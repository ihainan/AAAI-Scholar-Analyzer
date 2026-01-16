#!/usr/bin/env python3
"""
Compress oversized avatar images in the avatars directory.

This script scans all JPG/PNG images in data/aminer/avatars/ and compresses
any files larger than 1000KB by reducing quality while maintaining the original
format. The compressed images overwrite the original files.

Usage:
    # Compress all oversized avatars
    python compress_avatars.py

    # Dry run (show what would be compressed without actually compressing)
    python compress_avatars.py --dry-run

    # Custom size threshold (in KB)
    python compress_avatars.py --max-size 150

    # Custom quality settings
    python compress_avatars.py --jpg-quality 85 --png-quality 80
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow library is required. Install it with: pip install Pillow")
    sys.exit(1)


# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
AVATAR_DIR = PROJECT_ROOT / "data" / "aminer" / "avatars"

# Default settings
DEFAULT_MAX_SIZE_KB = 1000
DEFAULT_JPG_QUALITY = 85
DEFAULT_PNG_QUALITY = 80
MIN_QUALITY = 50  # Don't go below this to maintain reasonable image quality


def format_size(bytes_size: int) -> str:
    """Format bytes size to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f}TB"


def get_image_files() -> List[Path]:
    """Get all JPG and PNG files in the avatar directory."""
    if not AVATAR_DIR.exists():
        print(f"Error: Avatar directory not found: {AVATAR_DIR}")
        sys.exit(1)

    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        image_files.extend(AVATAR_DIR.glob(ext))

    return sorted(image_files)


def compress_image(
    image_path: Path,
    max_size_bytes: int,
    jpg_quality: int,
    png_quality: int,
    dry_run: bool = False
) -> Tuple[bool, int, int, str]:
    """
    Compress an image if it exceeds the maximum size.

    Args:
        image_path: Path to the image file
        max_size_bytes: Maximum allowed file size in bytes
        jpg_quality: JPEG compression quality (0-100)
        png_quality: PNG compression quality (0-100)
        dry_run: If True, don't actually compress the file

    Returns:
        Tuple of (was_compressed, original_size, new_size, message)
    """
    try:
        original_size = image_path.stat().st_size

        # Check if compression is needed
        if original_size <= max_size_bytes:
            return False, original_size, original_size, "Size OK"

        if dry_run:
            return True, original_size, 0, "Would compress (dry run)"

        # Open the image
        img = Image.open(image_path)

        # Convert RGBA to RGB for JPEG
        if img.mode in ('RGBA', 'LA', 'P') and image_path.suffix.lower() in ['.jpg', '.jpeg']:
            # Create a white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background

        # Determine file format and initial quality
        if image_path.suffix.lower() in ['.jpg', '.jpeg']:
            save_format = 'JPEG'
            quality = jpg_quality
            save_kwargs = {'format': save_format, 'quality': quality, 'optimize': True}
        else:  # PNG
            save_format = 'PNG'
            quality = png_quality
            save_kwargs = {'format': save_format, 'optimize': True, 'compress_level': 9}

        # Try to compress with decreasing quality until we meet the size requirement
        # or reach minimum quality
        temp_path = image_path.with_suffix(image_path.suffix + '.tmp')
        compressed = False

        while quality >= MIN_QUALITY:
            # Save with current quality settings
            if save_format == 'JPEG':
                save_kwargs['quality'] = quality
            elif save_format == 'PNG':
                # For PNG, use compression level (0-9, higher = more compression)
                # Quality parameter isn't standard for PNG, but we can adjust compression
                save_kwargs['compress_level'] = min(9, int((100 - quality) / 11) + 6)

            img.save(temp_path, **save_kwargs)
            new_size = temp_path.stat().st_size

            if new_size <= max_size_bytes:
                # Successfully compressed to target size
                temp_path.replace(image_path)
                compressed = True
                break

            # Reduce quality and try again
            quality -= 5

        # Clean up temp file if it still exists
        if temp_path.exists():
            if compressed:
                temp_path.replace(image_path)
            else:
                temp_path.unlink()

        if compressed:
            new_size = image_path.stat().st_size
            reduction_pct = ((original_size - new_size) / original_size) * 100
            return True, original_size, new_size, f"Compressed ({reduction_pct:.1f}% reduction)"
        else:
            return False, original_size, original_size, f"Failed to compress below {format_size(max_size_bytes)}"

    except Exception as e:
        return False, 0, 0, f"Error: {str(e)}"


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Compress oversized avatar images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=DEFAULT_MAX_SIZE_KB,
        help=f"Maximum file size in KB (default: {DEFAULT_MAX_SIZE_KB})"
    )
    parser.add_argument(
        "--jpg-quality",
        type=int,
        default=DEFAULT_JPG_QUALITY,
        help=f"Initial JPEG quality (0-100, default: {DEFAULT_JPG_QUALITY})"
    )
    parser.add_argument(
        "--png-quality",
        type=int,
        default=DEFAULT_PNG_QUALITY,
        help=f"Initial PNG quality reference (0-100, default: {DEFAULT_PNG_QUALITY})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be compressed without actually compressing"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.max_size <= 0:
        print("Error: max-size must be positive")
        sys.exit(1)
    if not (0 <= args.jpg_quality <= 100):
        print("Error: jpg-quality must be between 0 and 100")
        sys.exit(1)
    if not (0 <= args.png_quality <= 100):
        print("Error: png-quality must be between 0 and 100")
        sys.exit(1)

    max_size_bytes = args.max_size * 1024

    print(f"Scanning avatar directory: {AVATAR_DIR}")
    print(f"Maximum size threshold: {format_size(max_size_bytes)}")
    if args.dry_run:
        print("DRY RUN MODE: No files will be modified")
    print()

    # Get all image files
    image_files = get_image_files()
    if not image_files:
        print("No image files found")
        return

    print(f"Found {len(image_files)} image files")
    print()

    # Statistics
    stats = {
        "total": len(image_files),
        "compressed": 0,
        "skipped": 0,
        "failed": 0,
        "bytes_saved": 0
    }

    # Process each file
    for i, image_path in enumerate(image_files, 1):
        progress = (i / stats["total"]) * 100
        print(f"[{i}/{stats['total']} ({progress:.1f}%)] {image_path.name}", end=" ... ")

        was_compressed, original_size, new_size, message = compress_image(
            image_path,
            max_size_bytes,
            args.jpg_quality,
            args.png_quality,
            args.dry_run
        )

        if was_compressed:
            stats["compressed"] += 1
            if not args.dry_run:
                stats["bytes_saved"] += (original_size - new_size)
                print(f"✓ {message} [{format_size(original_size)} → {format_size(new_size)}]")
            else:
                print(f"→ {message} [{format_size(original_size)}]")
        elif "Error" in message:
            stats["failed"] += 1
            print(f"✗ {message}")
        else:
            stats["skipped"] += 1
            print(f"⊘ {message} [{format_size(original_size)}]")

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Total files:    {stats['total']}")
    print(f"  Compressed:     {stats['compressed']} ({stats['compressed']/stats['total']*100:.1f}%)")
    print(f"  Skipped:        {stats['skipped']} ({stats['skipped']/stats['total']*100:.1f}%)")
    print(f"  Failed:         {stats['failed']} ({stats['failed']/stats['total']*100:.1f}%)")
    if not args.dry_run and stats["bytes_saved"] > 0:
        print(f"  Space saved:    {format_size(stats['bytes_saved'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
