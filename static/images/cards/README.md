# Card Images

This directory is for custom card images.

## Directory Structure

```
cards/
├── placeholder/     # Placeholder images (optional)
├── spade/           # Spade suit cards
│   ├── 1.png        # Ace
│   ├── 2.png
│   ├── 3.png
│   ├── 4.png
│   ├── 5.png
│   └── 6.png
├── heart/           # Heart suit cards
│   └── ...
├── diamond/         # Diamond suit cards
│   └── ...
├── club/            # Club suit cards
│   └── ...
├── trump/           # Trump card
│   └── 0.png
└── back.png         # Card back design
```

## Image Specifications

- **Format**: PNG with transparency recommended
- **Size**: 70x98 pixels (or maintain 5:7 aspect ratio)
- **Resolution**: 72-144 DPI for web

## How to Add Custom Images

1. Create suit directories: `spade/`, `heart/`, `diamond/`, `club/`, `trump/`
2. Add numbered PNG files (1-6 for suits, 0 for trump)
3. Optionally add `back.png` for card back design
4. The UI will automatically use images if they exist

## CSS Integration

To enable image cards, the CSS class `.card.with-image` is provided.
Images are loaded via `background-image` property.

Example CSS override:
```css
.card[data-suit="spade"][data-rank="6"] {
    background-image: url('/static/images/cards/spade/6.png');
}
```

## Placeholder Mode

If no images are found, cards display as styled text with suit symbols.
This is the default behavior and requires no additional files.
