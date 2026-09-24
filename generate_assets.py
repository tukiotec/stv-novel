import os
from PIL import Image, ImageDraw, ImageFont

def generate_app_icon(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer rounded rectangle (Soft Enterprise Blue / Indigo)
    # Background badge
    badge_color = (37, 99, 235, 255) # #2563eb
    border_color = (30, 64, 175, 255) # #1e40af
    
    corner_radius = 48
    draw.rounded_rectangle([12, 12, size - 12, size - 12], radius=corner_radius, fill=badge_color, outline=border_color, width=4)

    # Draw book spine and pages
    # Left page
    draw.polygon([(48, 70), (124, 80), (124, 195), (48, 185)], fill=(255, 255, 255, 255))
    # Right page
    draw.polygon([(132, 80), (208, 70), (208, 185), (132, 195)], fill=(248, 250, 252, 255))

    # Inner book lines to simulate text
    for y in [105, 125, 145, 165]:
        draw.line([(60, y), (112, y + 5)], fill=(203, 213, 225, 255), width=3)
        draw.line([(144, y + 5), (196, y)], fill=(203, 213, 225, 255), width=3)

    # Bookmark ribbon (Amber / Gold #f59e0b)
    draw.polygon([(120, 60), (136, 60), (136, 120), (128, 112), (120, 120)], fill=(245, 158, 11, 255))

    # Save PNG
    png_path = os.path.join(output_dir, "stv_icon.png")
    img.save(png_path, "PNG")
    print(f"Saved icon PNG: {png_path}")

    # Save ICO with multiple sizes
    ico_path = os.path.join(output_dir, "stv_icon.ico")
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_path, format="ICO", sizes=icon_sizes)
    print(f"Saved icon ICO: {ico_path}")

if __name__ == "__main__":
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    generate_app_icon(assets_dir)
