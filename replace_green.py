import os
import re

directories = [
    r"c:\Users\Administrator\PycharmProjects\floki\templates",
    r"c:\Users\Administrator\PycharmProjects\floki\apps"
]

for d in directories:
    for root, _, files in os.walk(d):
        for file in files:
            if file.endswith('.html'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                new_content = content
                # 1. Backgrounds + Text combinations
                new_content = new_content.replace('bg-[#7c6af7] text-white', 'bg-brand-whatsapp text-black')
                # 2. Shadows
                new_content = new_content.replace('shadow-[0_0_15px_rgba(124,106,247,0.4)]', 'shadow-[0_0_15px_rgba(37,211,102,0.4)]')
                new_content = new_content.replace('shadow-[0_0_8px_rgba(124,106,247,0.5)]', 'shadow-[0_0_8px_rgba(37,211,102,0.5)]')
                # 3. Borders
                new_content = new_content.replace('border-[#7c6af7]', 'border-brand-whatsapp')
                # 4. Text colors
                new_content = new_content.replace('text-[#7c6af7]', 'text-brand-whatsapp')
                # 5. Backgrounds standalone
                new_content = new_content.replace('bg-[#7c6af7]', 'bg-brand-whatsapp')
                # 6. Any other stray #7c6af7
                new_content = new_content.replace('#7c6af7', '#25D366')

                if content != new_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
