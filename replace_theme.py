import os
import glob

template_dir = r"c:\Users\Administrator\PycharmProjects\floki\templates"
app_templates = r"c:\Users\Administrator\PycharmProjects\floki\apps"

for root, _, files in list(os.walk(template_dir)) + list(os.walk(app_templates)):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = content.replace('#7c6af7', '#25d366')
            new_content = new_content.replace('text-white', 'text-black')
            new_content = new_content.replace('text-text-primary', 'text-black')
            new_content = new_content.replace('bg-surface', 'bg-white')
            new_content = new_content.replace('bg-surface2', 'bg-[#F0F2F5]')
            
            if content != new_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
