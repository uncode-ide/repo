#!/usr/bin/env python3
"""
gen_index.py — Generates a simple HTML index for the APT repo
that gets deployed alongside the repo files on gh-pages.
"""

import os
import subprocess
import datetime
import glob

REPO_ROOT = "repo"
OUTPUT_FILE = os.path.join(REPO_ROOT, "index.html")

def get_packages():
    packages = []
    for deb in glob.glob("debs/*.deb"):
        try:
            result = subprocess.run(
                ["dpkg-deb", "--field", deb,
                 "Package", "Version", "Architecture", "Description"],
                capture_output=True, text=True, check=True
            )
            fields = {}
            for line in result.stdout.strip().splitlines():
                if ": " in line:
                    k, v = line.split(": ", 1)
                    fields[k.strip()] = v.strip()
            fields["_file"] = os.path.basename(deb)
            fields["_size"] = f"{os.path.getsize(deb) / 1024:.1f} KB"
            packages.append(fields)
        except Exception as e:
            print(f"Warning: could not read {deb}: {e}")
    return sorted(packages, key=lambda p: p.get("Package", ""))

def main():
    packages = get_packages()
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    rows = ""
    for p in packages:
        name = p.get("Package", "?")
        version = p.get("Version", "?")
        arch = p.get("Architecture", "?")
        desc = p.get("Description", "").split("\n")[0]
        size = p.get("_size", "?")
        rows += f"""
        <tr>
          <td><code>{name}</code></td>
          <td>{version}</td>
          <td>{arch}</td>
          <td>{desc}</td>
          <td>{size}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Uncode IDE — APT Repository</title>
  <style>
    :root {{
      --bg: #0d1117;
      --surface: #161b22;
      --border: #30363d;
      --accent: #58a6ff;
      --accent2: #3fb950;
      --text: #e6edf3;
      --muted: #8b949e;
      --code-bg: #1f2937;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, 'Segoe UI', sans-serif;
      line-height: 1.6;
      min-height: 100vh;
    }}
    header {{
      border-bottom: 1px solid var(--border);
      padding: 24px 48px;
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .logo {{
      width: 40px; height: 40px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-weight: 800; font-size: 18px; color: #0d1117;
    }}
    h1 {{ font-size: 1.4rem; font-weight: 700; }}
    h1 span {{ color: var(--muted); font-weight: 400; font-size: 0.9rem; }}
    main {{ max-width: 1000px; margin: 0 auto; padding: 48px 24px; }}
    .badge {{
      display: inline-block;
      background: var(--accent2);
      color: #0d1117;
      font-size: 0.72rem;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 20px;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      margin-left: 8px;
    }}
    .section-title {{
      font-size: 1rem;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 12px;
      margin-top: 40px;
    }}
    .install-box {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 24px;
      margin-bottom: 40px;
    }}
    .install-box h2 {{
      font-size: 1rem;
      color: var(--accent);
      margin-bottom: 16px;
    }}
    code {{
      font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
      font-size: 0.9rem;
    }}
    .cmd {{
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 10px 16px;
      margin: 8px 0;
      color: var(--accent2);
      display: block;
      overflow-x: auto;
    }}
    .cmd .prompt {{ color: var(--muted); user-select: none; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--surface);
      border-radius: 10px;
      overflow: hidden;
      border: 1px solid var(--border);
    }}
    thead {{ background: #21262d; }}
    th {{
      padding: 12px 16px;
      text-align: left;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-bottom: 1px solid var(--border);
    }}
    td {{
      padding: 12px 16px;
      font-size: 0.88rem;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: rgba(88,166,255,0.04); }}
    td code {{ color: var(--accent); }}
    .footer {{
      text-align: center;
      padding: 32px;
      color: var(--muted);
      font-size: 0.8rem;
      border-top: 1px solid var(--border);
      margin-top: 64px;
    }}
    .empty {{ color: var(--muted); text-align: center; padding: 40px; }}
  </style>
</head>
<body>
  <header>
    <div class="logo">U</div>
    <div>
      <h1>Uncode IDE APT Repository <span>· com.uncode.ide</span></h1>
    </div>
  </header>
  <main>
    <div class="install-box">
      <h2>⚡ Setup Instructions</h2>
      <p style="color:var(--muted); margin-bottom:14px; font-size:0.9rem;">
        Add this repository to your Uncode IDE terminal:
      </p>
      <code class="cmd">
        <span class="prompt">$ </span>echo "deb [trusted=yes] https://YOUR_GITHUB_USERNAME.github.io/YOUR_REPO_NAME uncode-stable main" &gt; $PREFIX/etc/apt/sources.list.d/uncode.list
      </code>
      <code class="cmd"><span class="prompt">$ </span>pkg update</code>
      <code class="cmd"><span class="prompt">$ </span>pkg install bash curl python vim</code>
      <p style="color:var(--muted); font-size:0.8rem; margin-top:12px;">
        Replace <code style="color:var(--accent)">YOUR_GITHUB_USERNAME</code> and <code style="color:var(--accent)">YOUR_REPO_NAME</code> with your actual GitHub details.
      </p>
    </div>

    <div class="section-title">Available Packages <span class="badge">{len(packages)} total</span></div>

    {"<p class='empty'>No packages built yet. Add a package to the packages/ directory and push.</p>" if not packages else f"""
    <table>
      <thead>
        <tr>
          <th>Package</th>
          <th>Version</th>
          <th>Arch</th>
          <th>Description</th>
          <th>Size</th>
        </tr>
      </thead>
      <tbody>{rows}
      </tbody>
    </table>"""}

    <div class="section-title" style="margin-top:48px;">Repository Info</div>
    <div class="install-box">
      <table style="border:none; background:transparent;">
        <tr>
          <td style="color:var(--muted); width:160px; border:none; padding: 6px 0;">Distribution</td>
          <td style="border:none; padding: 6px 0;"><code>uncode-stable</code></td>
        </tr>
        <tr>
          <td style="color:var(--muted); border:none; padding: 6px 0;">Component</td>
          <td style="border:none; padding: 6px 0;"><code>main</code></td>
        </tr>
        <tr>
          <td style="color:var(--muted); border:none; padding: 6px 0;">Architecture</td>
          <td style="border:none; padding: 6px 0;"><code>aarch64</code></td>
        </tr>
        <tr>
          <td style="color:var(--muted); border:none; padding: 6px 0;">Target App</td>
          <td style="border:none; padding: 6px 0;"><code>com.uncode.ide</code></td>
        </tr>
        <tr>
          <td style="color:var(--muted); border:none; padding: 6px 0;">Last Built</td>
          <td style="border:none; padding: 6px 0;"><code>{now}</code></td>
        </tr>
      </table>
    </div>
  </main>
  <div class="footer">
    Uncode IDE APT Repository · Built automatically by GitHub Actions · {now}
  </div>
</body>
</html>"""

    os.makedirs(REPO_ROOT, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)
    print(f"✓ Generated {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
