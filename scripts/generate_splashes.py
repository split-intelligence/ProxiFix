from PIL import Image, ImageOps
import os

sizes = [
    (640, 1136),
    (750, 1334),
    (1125, 2436),
    (1242, 2208),
    (828, 1792),
    (2048, 2732)
]

logo_path = os.path.join('marketplace', 'static', 'marketplace', 'images', 'handigo-logo.png')
out_dir = os.path.join('marketplace', 'static', 'marketplace', 'images')
bg_color = (13, 110, 253)  # #0d6efd

if not os.path.exists(out_dir):
    os.makedirs(out_dir, exist_ok=True)

for w, h in sizes:
    im = Image.new('RGB', (w, h), bg_color)
    try:
        logo = Image.open(logo_path).convert('RGBA')
        # scale logo to 40% of width
        lw = int(w * 0.4)
        ratio = lw / logo.width
        lh = int(logo.height * ratio)
        logo = logo.resize((lw, lh), Image.LANCZOS)
        x = (w - lw) // 2
        y = (h - lh) // 2
        im.paste(logo, (x, y), logo)
    except Exception as e:
        # If logo load fails, leave plain background
        print(f"Could not open logo: {e}")
    out_path = os.path.join(out_dir, f'ios-splash-{w}x{h}.png')
    im.save(out_path)
    print('Saved', out_path)

print('All splash images generated.')
