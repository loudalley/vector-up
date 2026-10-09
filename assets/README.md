# Brand resources

Koenekt and Vector logos supplied by the project owner for this app. The full
Koenekt logo preserves the original lettering and mark. PNGs are packaged UI
resources, not executable build outputs. No customer data is included.

`koenekt-fade.png` is a strip of 21 opacity frames, each 1320 by 340 pixels,
on white. Tk displays these at half size; no runtime imaging dependency is
needed. `koenekt-header.png` and `vector.png` are also prepared at double size.

To regenerate from the supplied transparent logo PNGs, install Pillow in a
development environment and run:

```
python tools/prepare_branding.py koenekt-logo.png vector-logo.png
```

Theme geometry is drawn by the app; the reference pattern images are not
distributed. Colours and typography remain in `techtool/gui.py`.
