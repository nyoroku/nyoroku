import os

files = [
    r"c:\Users\Administrator\PycharmProjects\floki\templates\pos\index.html",
    r"c:\Users\Administrator\PycharmProjects\floki\templates\pos\partials\product_grid.html",
    r"c:\Users\Administrator\PycharmProjects\floki\templates\pos\partials\receipt_modal.html"
]

for f in files:
    try:
        # Try reading as cp1252 (PowerShell's default) to fix if it was written this way
        with open(f, 'r', encoding='mbcs') as file:
            content = file.read()
            
        # Write back explicitly as UTF-8 without BOM
        with open(f, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"Fixed {f}")
    except Exception as e:
        print(f"Error on {f}: {e}")
