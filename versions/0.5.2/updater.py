from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

APP_NAME = 'Soares Soluções'
DEFAULT_MANIFEST_URL = 'https://raw.githubusercontent.com/joesoares94-blip/-soares-solucoes-updates/main/update.json'
TIMEOUT_SECONDS = 12


def _parts(version: str) -> tuple[int, ...]:
    cleaned = (version or '').strip().lower().lstrip('v')
    values: list[int] = []
    for part in cleaned.split('.'):
        digits = ''.join(ch for ch in part if ch.isdigit())
        values.append(int(digits or '0'))
    while len(values) < 3:
        values.append(0)
    return tuple(values)


def is_newer(remote: str, current: str) -> bool:
    return _parts(remote) > _parts(current)


def get_manifest_url() -> str:
    env_url = os.environ.get('SOARES_SOLUCOES_UPDATE_URL', '').strip()
    if env_url:
        return env_url
    cfg = Path(__file__).with_name('update_config.json')
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding='utf-8'))
            value = str(data.get('manifest_url') or '').strip()
            if value:
                return value
        except Exception:
            pass
    return DEFAULT_MANIFEST_URL


def fetch_manifest(current_version: str) -> dict[str, Any]:
    url = get_manifest_url()
    req = urllib.request.Request(url, headers={'User-Agent': f'SoaresSolucoes/{current_version}'})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        if resp.status != 200:
            raise RuntimeError(f'Servidor de atualização respondeu HTTP {resp.status}.')
        raw = resp.read(256 * 1024)
    data = json.loads(raw.decode('utf-8-sig'))
    remote = str(data.get('version') or '').strip()
    files = data.get('files')
    package_url = str(data.get('url') or '').strip()
    sha256 = str(data.get('sha256') or '').strip().lower()
    has_files = isinstance(files, list) and bool(files)
    has_package = bool(package_url) and len(sha256) == 64
    if not remote or not (has_files or has_package):
        raise RuntimeError('O arquivo de atualização publicado está incompleto.')
    data['available'] = is_newer(remote, current_version)
    data['manifest_url'] = url
    return data


def _download_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': 'SoaresSolucoes-Updater'})
    with urllib.request.urlopen(req, timeout=120) as resp:
        if resp.status != 200:
            raise RuntimeError(f'Falha no download: HTTP {resp.status}.')
        return resp.read(16 * 1024 * 1024)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().lower()

def _installed_paths() -> tuple[Path, Path, Path]:
    app_dir = Path(__file__).resolve().parent
    root = app_dir.parent
    launcher = root / 'Soares Solucoes.exe'
    return app_dir, root, launcher


def download_and_prepare(manifest: dict[str, Any]) -> Path:
    work = Path(tempfile.mkdtemp(prefix='soares_update_'))
    extracted = work / 'payload'
    extracted.mkdir()

    files = manifest.get('files')
    if isinstance(files, list) and files:
        for item in files:
            if not isinstance(item, dict):
                raise RuntimeError('Lista de arquivos da atualização inválida.')
            name = str(item.get('name') or '').strip().replace('\', '/')
            url = str(item.get('url') or '').strip()
            expected = str(item.get('sha256') or '').strip().lower()
            if not name or name.startswith('/') or '..' in Path(name).parts or not url or len(expected) != 64:
                raise RuntimeError('Arquivo de atualização inválido.')
            data = _download_bytes(url)
            if _sha256(data) != expected:
                shutil.rmtree(work, ignore_errors=True)
                raise RuntimeError(f'A verificação de segurança falhou para {name}.')
            target = extracted / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    else:
        archive = work / 'update.zip'
        expected = str(manifest['sha256']).lower()
        data = _download_bytes(str(manifest['url']))
        if _sha256(data) != expected:
            shutil.rmtree(work, ignore_errors=True)
            raise RuntimeError('A atualização baixada falhou na verificação de segurança (SHA-256).')
        archive.write_bytes(data)
        with zipfile.ZipFile(archive, 'r') as zf:
            for info in zf.infolist():
                target = (extracted / info.filename).resolve()
                if extracted.resolve() not in target.parents and target != extracted.resolve():
                    raise RuntimeError('Pacote de atualização inválido.')
            zf.extractall(extracted)

    if not any(extracted.rglob('*')):
        shutil.rmtree(work, ignore_errors=True)
        raise RuntimeError('A atualização não contém arquivos para aplicar.')
    return work

def launch_apply_script(work_dir: Path, new_version: str) -> None:
    app_dir, root, launcher = _installed_paths()
    if not launcher.exists():
        raise RuntimeError('Atualização automática só pode ser aplicada na versão instalada do Windows.')
    payload = work_dir / 'payload'
    script = work_dir / 'aplicar_atualizacao.ps1'
    content = f'''$ErrorActionPreference = "Stop"
Start-Sleep -Seconds 2
$src = {json.dumps(str(payload))}
$dst = {json.dumps(str(app_dir))}
$root = {json.dumps(str(root))}
$launcher = {json.dumps(str(launcher))}
$version = {json.dumps(str(new_version))}
Get-ChildItem -LiteralPath $src -Force | ForEach-Object {{
    $target = Join-Path $dst $_.Name
    if ($_.PSIsContainer) {{
        Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse -Force
    }} else {{
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }}
}}
Set-Content -LiteralPath (Join-Path $root 'version.txt') -Value $version -Encoding ASCII
Start-Process -FilePath $launcher
Start-Sleep -Seconds 1
Remove-Item -LiteralPath {json.dumps(str(work_dir))} -Recurse -Force -ErrorAction SilentlyContinue
'''
    script.write_text(content, encoding='utf-8-sig')
    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    subprocess.Popen(
        ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
        cwd=str(root),
        creationflags=creationflags,
    )


def apply_update_and_exit(manifest: dict[str, Any]) -> None:
    work = download_and_prepare(manifest)
    launch_apply_script(work, str(manifest['version']))
    os._exit(0)


def _install_frontend_hook():
    try:
        import tkinter as tk
        original = tk.Tk.mainloop
        if getattr(original, '_soares_v052', False):
            return
        def patched_mainloop(self, *args, **kwargs):
            try:
                import frontend_v052
                frontend_v052.apply(self)
            except Exception:
                pass
            return original(self, *args, **kwargs)
        patched_mainloop._soares_v052 = True
        tk.Tk.mainloop = patched_mainloop
    except Exception:
        pass

_install_frontend_hook()
