from PIL import Image, ImageDraw, ImageFont
import os

def create_gold_icon(size=512):
    # Create image with RGBA
    img = Image.new('RGBA', (size, size), (11, 15, 25, 255)) # Dark slate base
    draw = ImageDraw.Draw(img)

    pad = int(size * 0.08)
    # Outer luxury gold rounded rect / shield
    bbox = [pad, pad, size - pad, size - pad]
    radius = int(size * 0.22)
    
    # Outer dark gold glow / border
    draw.rounded_rectangle(bbox, radius=radius, fill=(24, 32, 47, 255), outline=(245, 158, 11, 255), width=max(2, int(size * 0.02)))

    # Inner circular golden shield
    circle_pad = int(size * 0.18)
    circle_bbox = [circle_pad, circle_pad, size - circle_pad, size - circle_pad]
    
    # Gold gradient simulation (solid luxury amber with inner accent)
    draw.ellipse(circle_bbox, fill=(217, 119, 6, 255), outline=(251, 191, 36, 255), width=max(2, int(size * 0.025)))

    # Draw "Au" text
    # Try default font with large scale or drawn glyphs
    font_size = int(size * 0.32)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()

    text = "Au"
    # Center text
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_w = right - left
        text_h = bottom - top
    except:
        text_w = font_size
        text_h = font_size

    text_x = (size - text_w) / 2
    text_y = (size - text_h) / 2 - int(size * 0.04)

    # Text shadow
    draw.text((text_x + 2, text_y + 3), text, fill=(120, 53, 15, 255), font=font)
    # Bright gold text
    draw.text((text_x, text_y), text, fill=(255, 251, 235, 255), font=font)

    # Subtext "79" (Gold atomic number) or gold bar line
    bar_y = int(size * 0.72)
    bar_w = int(size * 0.28)
    bar_x = (size - bar_w) / 2
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + max(4, int(size * 0.02))], radius=2, fill=(254, 243, 199, 255))

    return img

def main():
    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    os.makedirs(target_dir, exist_ok=True)

    icon_512 = create_gold_icon(512)
    icon_512.save(os.path.join(target_dir, "icon-512.png"))

    icon_192 = create_gold_icon(192)
    icon_192.save(os.path.join(target_dir, "icon-192.png"))

    icon_180 = create_gold_icon(180)
    icon_180.save(os.path.join(target_dir, "apple-touch-icon.png"))
    icon_180.save(os.path.join(target_dir, "apple-touch-icon-precomposed.png"))

    # Also save as favicon
    icon_64 = create_gold_icon(64)
    icon_64.save(os.path.join(target_dir, "favicon.ico"), format="ICO")

    print("All professional icons generated in static/ folder!")

if __name__ == "__main__":
    main()
