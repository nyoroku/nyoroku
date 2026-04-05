import os
import re

directories = [
    r"c:\Users\Administrator\PycharmProjects\floki\templates"
]

for d in directories:
    for root, _, files in os.walk(d):
        for file in files:
            if file.endswith('.html'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                new_content = content
                new_content = new_content.replace('bg-brand-whatsapp text-black', 'bg-brand-whatsapp text-white')

                if content != new_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
