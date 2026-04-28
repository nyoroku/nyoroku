
import os

target = 'templates/pos/index.html'

with open(target, 'rb') as f:
    content = f.read()

# Replacements (Bad UTF-8 bytes -> Good UTF-8 bytes)
replacements = [
    (b'\xc3\xa2\xe2\x80\xa2\xc3\xa2\xe2\x80\xa2\xc3\xa2\xe2\x80\xa2', b'\xe2\x95\x90\xe2\x95\x90\xe2\x95\x90'), # â•â•â• -> ═══
    (b'\xc3\xb0\xc5\xb8\xe2\x80\x9b\xe2\x80\x98', b'\xf0\x9f\x9b\x92'), # ðŸ›’ -> 🛒
    (b'\xc3\xa2\xe2\x82\xac\xe2\x80\x9d', b'\xe2\x80\x94'), # â€” -> —
    (b'\xc3\xa2\xc5\x93\xe2\x80\xa2', b'\xe2\x9c\x95'), # âœ• -> ✕
    (b'\xc3\xb0\xc5\xb8\xc5\xb8\xc2\xa2', b'\xf0\x9f\x9f\xa2'), # ðŸŸ¢ -> 🟢
    (b'\xc3\xa2\x22\x20\xe2\x82\xac', b'\xe2\x94\x80'), # â"€ -> ─
    (b'\xc3\xb0\xc5\xb8\xe2\x80\x99\xc2\xb5', b'\xf0\x9f\x92\xb5'), # ðŸ’µ -> 💵
    (b'\xc3\xb0\xc5\xb8\xe2\x80\x9c\xc2\xb1', b'\xf0\x9f\x93\xb1'), # ðŸ“± -> 📱
    (b'\xc3\xb0\xc5\xb8\xe2\x80\x99\xc2\xb3', b'\xf0\x9f\x92\xb3'), # ðŸ’³ -> 💳
    (b'\xc3\xa2\xc5\xa1\xe2\x80\x93', b'\xe2\x9a\x96'), # âš– -> ⚖
    (b'\xc3\xa2\xc5\x93\x22', b'\xe2\x9c\x93'), # âœ" -> ✓
    (b'\xc3\xa2\xc2\xb3', b'\xe2\x8c\x9b'), # â³ -> ⌛
    (b'\xc3\xa2\xe2\x80\xa0\xe2\x80\x99', b'\xe2\x86\x92'), # â†’ -> →
    (b'\xc3\xa2\xc5\x92\xc2\xab', b'\xe2\x8c\xab'), # âŒ« -> ⌫
    (b'\xc3\x83\xe2\x80\x94', b'\xc3\x97'), # Ã— -> ×
]

for bad, good in replacements:
    content = content.replace(bad, good)

# Also handle cases where they are already in "utf-8" string form but corrupted
# This is tricky without knowing the exact current byte state.
# Let's try a direct string replacement for common ones if they survive the write.

text = content.decode('utf-8', errors='ignore')

# String based cleanups for common patterns seen in previous output
text = text.replace('â• â• â•', '───')
text = text.replace('ðŸ›’', '🛒')
text = text.replace('âœ•', '✕')
text = text.replace('ðŸŸ¢', '🟢')
text = text.replace('ðŸ’µ', '💵')
text = text.replace('ðŸ“±', '📱')
text = text.replace('ðŸ’³', '💳')
text = text.replace('âš–', '⚖')
text = text.replace('âœ"', '✓')
text = text.replace('â³', '⌛')
text = text.replace('â†’', '→')
text = text.replace('âŒ«', '⌫')
text = text.replace('Ã—', '×')
text = text.replace('â€”', '—')

with open(target, 'w', encoding='utf-8') as f:
    f.write(text)

print("Finished fixing encoding.")
