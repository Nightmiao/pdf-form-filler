"""遍历 staging 目录，为每个文件生成 WiX v4 Component 元素"""
import os
import uuid

STAGING_DIR = os.path.join(os.path.dirname(__file__), 'installer', 'staging', 'FormFillerApp')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), 'installer', 'app-components.wxs')


def generate_guid(seed: str) -> str:
    """基于文件路径生成确定性 GUID"""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"form-filler:{seed}")).upper()


def generate_components():
    lines = []
    lines.append('<?xml version="1.0" encoding="utf-8"?>')
    lines.append('<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">')
    lines.append('  <Fragment>')
    lines.append('    <ComponentGroup Id="AppComponents" Directory="INSTALLFOLDER">')

    for root, dirs, files in os.walk(STAGING_DIR):
        for filename in files:
            full_path = os.path.join(root, filename)
            relative_dir = os.path.relpath(root, STAGING_DIR).replace('\\', '/')
            if relative_dir == '.':
                relative_dir = ''

            # 构建相对于 INSTALLFOLDER 的子目录路径
            if relative_dir:
                source_path = f"$(var.StagingDir)\\{relative_dir}\\{filename}"
            else:
                source_path = f"$(var.StagingDir)\\{filename}"

            # 生成唯一的组件 ID
            file_key = f"{relative_dir}/{filename}" if relative_dir else filename
            comp_id = "cmp" + generate_guid(file_key).replace('-', '')[:12]

            guid = generate_guid(file_key)

            if relative_dir:
                # 文件在子目录中 — 需要创建子目录并放置文件
                dir_id = "dir" + generate_guid(relative_dir).replace('-', '')[:10]
                subdir_path = relative_dir.replace('/', '\\')

                lines.append(f'      <!-- {subdir_path}\\{filename} -->')
                lines.append(f'      <Directory Id="{dir_id}" Name="{os.path.basename(relative_dir)}">')
                lines.append(f'        <Component Id="{comp_id}" Guid="{guid}" Subdirectory="{subdir_path}">')
                lines.append(f'          <File Id="file{comp_id}" Source="{source_path}" KeyPath="yes" />')
                lines.append(f'        </Component>')
                lines.append(f'      </Directory>')
            else:
                # 文件在根目录
                lines.append(f'      <Component Id="{comp_id}" Guid="{guid}">')
                lines.append(f'        <File Id="file{comp_id}" Source="{source_path}" KeyPath="yes" />')
                lines.append(f'      </Component>')

    lines.append('    </ComponentGroup>')
    lines.append('  </Fragment>')
    lines.append('</Wix>')

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"已生成组件清单: {OUTPUT_FILE}")
    print(f"共处理 {len([l for l in lines if '<Component Id=' in l])} 个文件")


if __name__ == '__main__':
    generate_components()
