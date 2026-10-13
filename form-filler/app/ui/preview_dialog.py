"""预览对话框 — 弹窗显示填好的 PDF 效果，可缩放、导出或打印"""

from __future__ import annotations

import tempfile
import os
from app.qt import QtWidgets, QtCore, Qt, dialog_exec
from app.ui.theme import apply_role, icon_of
from app.core.pdf_engine import burn_text, pdf_to_images

QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QLabel = QtWidgets.QLabel
QScrollArea = QtWidgets.QScrollArea
QWidget = QtWidgets.QWidget
QHBoxLayout = QtWidgets.QHBoxLayout
QPushButton = QtWidgets.QPushButton
QFileDialog = QtWidgets.QFileDialog
QMessageBox = QtWidgets.QMessageBox
QApplication = QtWidgets.QApplication


class PreviewDialog(QDialog):
    """填好的 PDF 预览对话框（带缩放）"""

    PREVIEW_DPI = 150

    def __init__(self, template, record, template_manager, parent=None,
                 before_export=None):
        super().__init__(parent)
        self._template = template
        self._record = record
        self._template_manager = template_manager
        # 导出/打印前的校验回调（返回 True 才继续）。
        # 历史缺陷：预览弹窗里的"导出 PDF / 打印"完全绕过了必填校验，
        # 同一条路径在主界面会被拦下，在这里却直接放行。
        self._before_export = before_export
        self._output_path = ""
        self._failed = False
        self._export_btn = None
        self._print_btn = None
        self._images = []
        self._page_labels = []
        self._zoom_factor = 1.0  # 1.0 = 适应宽度
        # 真防抖：成员级 singleShot 定时器，连续 resize 时不断重启计时
        self._resize_timer = QtCore.QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(80)
        self._resize_timer.timeout.connect(self._apply_zoom)
        self._setup_ui()
        try:
            self._build_preview()
            self._apply_zoom()
        except Exception as e:
            # PDF 损坏等原因导致预览失败时，界面上给出反馈而不是静默崩溃
            self._failed = True
            error = QLabel(f"生成预览失败：{e}")
            error.setProperty("role", "error")
            error.setWordWrap(True)
            error.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content_layout.addWidget(error)
            if self._export_btn is not None:
                self._export_btn.setEnabled(False)
            if self._print_btn is not None:
                self._print_btn.setEnabled(False)

    def _setup_ui(self):
        self.setWindowTitle(f"预览 - {self._template.name}")
        screen = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        if screen:
            self.resize(
                min(900, screen.width() - 160),
                min(1000, screen.height() - 160),
            )
        else:
            self.resize(820, 940)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 顶部：说明 + 缩放
        head = QHBoxLayout()
        info = QLabel(
            f"{self._template.name} · 共 {self._template.page_count} 页 · "
            f"填写内容将烧录进 PDF（原始文件不受影响）"
        )
        info.setProperty("role", "hint")
        head.addWidget(info)
        head.addStretch()

        self._zoom_out_btn = QPushButton("−")
        apply_role(self._zoom_out_btn, "toolbar")
        self._zoom_out_btn.setFixedWidth(28)
        self._zoom_out_btn.setToolTip("缩小")
        self._zoom_out_btn.clicked.connect(self._zoom_out)
        head.addWidget(self._zoom_out_btn)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(44)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_label.setStyleSheet("color:#374151; font-weight:600;")
        self._zoom_label.setToolTip("100% = 适应窗口宽度；点 + / − 可放大缩小预览")
        head.addWidget(self._zoom_label)

        self._zoom_in_btn = QPushButton("＋")
        apply_role(self._zoom_in_btn, "toolbar")
        self._zoom_in_btn.setFixedWidth(28)
        self._zoom_in_btn.setToolTip("放大")
        self._zoom_in_btn.clicked.connect(self._zoom_in)
        head.addWidget(self._zoom_in_btn)

        fit_btn = QPushButton("适应宽度")
        apply_role(fit_btn, "toolbar")
        fit_btn.setToolTip("恢复适应宽度")
        fit_btn.clicked.connect(self._zoom_fit)
        head.addWidget(fit_btn)

        layout.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setSpacing(10)
        self.scroll.setWidget(self._content)
        layout.addWidget(self.scroll, stretch=1)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        btns.addStretch()
        export_btn = QPushButton("导出 PDF")
        apply_role(export_btn, "primary")
        export_btn.setIcon(icon_of(self, "SP_DialogSaveButton"))
        export_btn.clicked.connect(self._export)
        self._export_btn = export_btn
        btns.addWidget(export_btn)
        print_btn = QPushButton("打印")
        print_btn.setIcon(icon_of(self, "SP_ComputerIcon"))
        print_btn.clicked.connect(self._print)
        self._print_btn = print_btn
        btns.addWidget(print_btn)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)
        layout.addLayout(btns)

        self.finished.connect(self._cleanup)

    def _build_preview(self):
        pdf_path = self._template_manager.pdf_path(self._template.id)
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.close()
        self._output_path = burn_text(
            pdf_path,
            self._template.fields,
            self._record.values,
            self._template.page_settings,
            tmp.name,
        )

        # 自检：有填写内容但烧录结果提取不到文字 → 明确报错而不是展示空白页
        values = self._record.values or {}
        if any(str(v).strip() for v in values.values()):
            import fitz
            _chk = fitz.open(self._output_path)
            _text = "".join(pg.get_text() for pg in _chk).strip()
            _chk.close()
            if not _text:
                raise RuntimeError(
                    "填写内容未能写入预览文件（PDF 可能受保护）。\n"
                    "请先使用「导出 PDF」检查填写内容。"
                )

        self._images = pdf_to_images(self._output_path, dpi=self.PREVIEW_DPI)
        self._page_labels = []
        for i, img in enumerate(self._images):
            page_label = QLabel(f"第 {i + 1} 页")
            page_label.setProperty("role", "meta")
            self._content_layout.addWidget(page_label)
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content_layout.addWidget(lbl)
            self._page_labels.append(lbl)

    # ── 缩放 ──────────────────────────────────────

    def _fit_scale(self) -> float:
        if not self._images:
            return 1.0
        vp = max(120, self.scroll.viewport().width() - 30)
        return vp / max(img.width() for img in self._images)

    def _apply_zoom(self):
        if self._failed or not self._images:
            return
        scale = self._fit_scale() * self._zoom_factor
        for img, lbl in zip(self._images, self._page_labels):
            lbl.setPixmap(
                img.scaled(
                    max(1, int(img.width() * scale)),
                    max(1, int(img.height() * scale)),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self._zoom_label.setText(f"{int(self._zoom_factor * 100)}%")

    def _zoom_in(self):
        self._zoom_factor = min(3.0, self._zoom_factor * 1.25)
        self._apply_zoom()

    def _zoom_out(self):
        self._zoom_factor = max(0.25, self._zoom_factor / 1.25)
        self._apply_zoom()

    def _zoom_fit(self):
        self._zoom_factor = 1.0
        self._apply_zoom()

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._apply_zoom)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 真防抖：重启计时器，只有停止拖拽 80ms 后才执行一次全量重缩放
        self._resize_timer.start()

    # ── 导出 / 打印 ───────────────────────────────

    def _passes_required_check(self) -> bool:
        """必填校验（与主界面导出/打印同一套），未通过则中断本次操作"""
        if self._before_export is None:
            return True
        try:
            return bool(self._before_export())
        except Exception:
            return True

    def _export(self):
        if self._failed or not self._output_path:
            return
        if not self._passes_required_check():
            return
        default_name = f"{self._template.name}_已填写.pdf"
        original = os.path.normcase(os.path.abspath(
            self._template_manager.pdf_path(self._template.id)
        ))
        for attempt in range(2):
            filepath, _ = QFileDialog.getSaveFileName(
                self, "导出填好的 PDF", default_name, "PDF 文件 (*.pdf)"
            )
            if not filepath:
                return
            if os.path.normcase(os.path.abspath(filepath)) == original:
                QMessageBox.warning(
                    self, "不能覆盖原文件",
                    "导出的 PDF 不能与模板原始文件保存在同一路径，\n"
                    "请换个文件名或位置。",
                )
                continue
            try:
                import shutil
                shutil.copy2(self._output_path, filepath)
                QMessageBox.information(self, "导出成功", f"PDF 已保存到：\n{filepath}")
                return
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))
                return

    def _print(self):
        if self._failed:
            return
        if not self._passes_required_check():
            return
        from app.ui.print_helper import print_filled_pdf
        print_filled_pdf(
            self._template, self._record, self._template_manager, self
        )

    def _cleanup(self):
        if self._output_path and os.path.exists(self._output_path):
            try:
                os.unlink(self._output_path)
            except OSError:
                pass