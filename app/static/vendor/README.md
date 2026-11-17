# Offline Vendor Assets

This directory contains vendored third-party frontend libraries for offline operation.

## Vendored Assets

1. **Bootstrap 5.3.3**
   - `bootstrap/css/bootstrap.min.css` (MIT License)
   - `bootstrap/js/bootstrap.bundle.min.js` (MIT License)

2. **Bootstrap Icons 1.11.3**
   - `bootstrap-icons/bootstrap-icons.svg` (MIT License)

3. **Chart.js 4.4.7**
   - `chartjs/chart.umd.min.js` (MIT License)
   - UMD minified build from Chart.js v4.4.7 official release.

## Verification Command

Run the following Python command to verify presence of all required offline assets:

```bash
python -c "import pathlib; paths = ['app/static/vendor/bootstrap/css/bootstrap.min.css', 'app/static/vendor/bootstrap/js/bootstrap.bundle.min.js', 'app/static/vendor/chartjs/chart.umd.min.js']; print([pathlib.Path(p).exists() for p in paths])"
```
Expected output: `[True, True, True]` (or with bootstrap-icons if included).
