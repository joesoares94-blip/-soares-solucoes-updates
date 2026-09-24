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
            name = str(item.get('name') or '').strip().replace('\\', '/')
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
    # O banco está em %LOCALAPPDATA%\\Soares Solucoes e, portanto, fora da pasta app.
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
    # Fecha todo o processo Python/Tk para liberar os arquivos que serão substituídos.
    os._exit(0)

# Bootstrap transitório da v0.5.2: permite que instalações v0.5.1
# recebam a nova interface sem baixar um instalador completo.
def _bootstrap_v052_app():
    try:
        app_path = Path(__file__).with_name('app.py')
        current = app_path.read_text(encoding='utf-8') if app_path.exists() else ''
        if "VERSION = '0.5.2'" in current:
            return
        import base64 as _b64, zlib as _zlib
        payload = 'eNrNfV1v48iW2Lt/BdOTgNKMRleSP9rtXG3gttVzjZ1u97W7596F2yAoqSRzTJEakvLHdBqYp93nBJsAWSQIJotgcRfYp4u85NX/ZH5BfkLOOVVFVhWLFOXunr3GTEsi6+NU1anzXadmSbxwPG+2ylYJ8zwnWCzjJHP8KIozPwviKN0Sj7LrIMpY4vgpfN2aYT35SJbIrjvOgqWpP2fj+K7jzIKQTQM/jOeykR9WbMXyFq8S5k+DKH879lO2t8PbXvrZVRiMZduv4efWFn819TMfi8p3QRRk3nQsW/FXUFR8T1lyE0xYyiuyuwkLPVlL/fDuwvSOF0oYPkjle3ZH79Msnlx7y+lMtrxaAhgs2do6fP3ae3Py5tuRM3Tc89hPWOqcx+Hq4Z8e/g9L3a3vRmfnJ6ev8G2vu9sduFuvDr/7G/z5Re/F4OnOU/5gQE/6L3ZGT5+5W8+/oZ8vdl7svdh3t96M/viGv386eL5z7G69fPtmdExP9vae9vZ33a0//O7kzYhXoj9o4/TseHRGj0bQ6ujI3Tp/e3Q0Oj/nTe0+3cbOjw9ffSOKPd8ZbPehu0Mo9Yp3OHix38PGvj395uSV983Z4fEJvPLO3xye8QK95/0Xu6NSgdErDt7g+fNtrP/65NVfC+i2n+/DCLbOTr8ded8ePh99i/C833Lgzz39w6vRmXvguK+TeJkELHv4OQlit8PfHh6/PHmFbw+nC1j0NEv8aZzIt6evR2eHb06p+umSae++Oxn9gTd8BCi9CjMf3nzgMLw4O33JAUE4bg6ca2cWJw7g8g2glqPA2Q0ytkhb7Q+AiZPQT1PncLlsZdfdN9ftA+poymawmwghvVbKwpl4jn/pCoBqtbv5+3bxCkp2syALWWvmvs8x6oPzy09/7wDEWRKHDBp3RoCHsIfcomqW3Bdd4F/l7lELUYfBJI7GQbbwly2A24dZGcKUtrBwC0gCbF7Pa3dvg+zKi/wFa7kpYbeXAnZPYpZiA267XcCC+2uZOSP6ANqhA7aECdNHPGfxgsEAWm5/MOjdPd3rucacwDKnwY+s1e8Neh1nb7dnvIcRzII5kK7WeD58/o35dpUkLMq8FZABWNtXccT0AnwTe0SVoAB9dn+P/5qL44mikysGdCDN/CRjU6jywg/TolFBiUqV0+w+LDWZXsW3nj8B6gRTOkkYi6BEgUW8jolD+BC6BVLbPS8K6O+72RVbMBx1ywU0Xbjm+2LW3DfQ703Abt0OUN/J9TyJV9F06N5eAaq7SMFZOLW+iBMmniFx6mgrrf4l8e0VC+ZX2XAbVnAcJ1OW3AbT7GrYawBW93ecQ+jgIb3UQJBgVUIxgz00bLnnbB4z5+0JNNcHaNxxHE7ddgdofhiw2dCdhX5Wmi3cHxXzdAF7goVsArgAL4iMty81yPQSAs72Zd3QR7Dd76Hw0p/i0IdP6wofxYtxDMxWKb+nYBFsV5Z5SRxnJiYhiYN1mDPknxwhb4NoFgOGB+E0QWTUty8v3J0yoBHxvYqqFkQ20RabV2ApRhTMiF93r/yUtmlqdltsFRAjgkipymDnVZWdBUmaefFtxBIPel0tta01Tfxbbw4MIgDqQLB2nIkf3fgpfMZhnPTF56DjEK52HI7DCmzY0BW787LYS+bj1o0frpgBOj2DzUqf3RDmLQBM+kJBMNogAF4SOQAj7GaQp3hTF8FB8NUAcKm/16a1CnCZWoC0ANNOW4yG6gOwc/h/3IeuFIj4QIq+cDBz+H88sJQbqDjGlikUWfh3LTF4pZUclMSP5kB9sLAx7ATlRmggcH5DjfAGv3b6WkP4FyFVxiEnfecrp5UMoBSA7HzJ2zAKz0XhORWeY+F5ZeGxKDymwmMsPK4qTDMA5WdPvngfJQe9wd2H99FcfI7p84legXClC6iOLCEMIli4jgNrE0hEIdk3HFLLKubJXXLFwlAgHrH9A5j2pAMiwrj4qe4fLI9k/7r7IkFWzKsCzyOxr60X7C6BQrUIAKBw2RXQBpBifSTVCSBpgTohm2Vaq1jb1iwW5K2mwZQNXfztijFauiBadDdsbe8R/tLP++FgoHQNfX7rj1nYwqZgEthdNnTPTw/PRuduAQF0Mc+pvUnBt3dyCt7mwPnR5CpOgBu4osvWLiyLIqBU9Prt24e/e/gv9p4Htq77++u7BnTo76zr+9XDn1PQZ5yS3vAOFKtFnDqxE4+/Z1lwEwMC2RicZaq+X6VZMLsvlqkE/2BQDf8aiGf+JAgDkH8AtJStHNDvHB//7byLgii+ARyIHQa6IZtEMZJs/13EnDQfWHftILj28bHDkMsARfoDlV6O4+m9ivR8cGWcx3LrdlJOFYEQrHABlXaxvq1dWdaynyT0UQ79Tg8RWO6nnhhLzjxRHYE+L7QZbbm//MN/Q2HjTb4E+AuEWycFfSAMZsHEB6nHrPRf/zcWU1RXUWkOqhSqxaQ2TeO0XPX//c//RHVf+8mEJbw7QIGJD5jNMn+p9Xap8xIQZgQN9BDBOoDm6QQZDA3O4CzxrTrDciZtsyyKV2BFv6eXzDEdqghE54BBw6A9H71AHVZDTgMZndEi/j4gytAWMsNw0LYscbGQKl0iGO40WkyQ2McFJUstV4wnu5MbV53iRuS1329CIyp6w0U0+iGThbWjnq0DXXYk2c9bXsUgtASLuanM8Reo9MKbav1VaaU7D2auJoZGcaa002V3QZqVpNGSts0VW7QXDYHIoVJo6s/wFqTM7jyMxzoE470dfJl96RqYIACiZg+sKg2LJvGU9E/X7X4fg1iMhbtoTqMlblEBVAZcP50EgdvucumTy5JYGLcY9dC29qDMxG0CW9Eb32csbXELHYI+ZQhCS0BijKDeEFAyBuBgHzXzHBUA/15j9ZOFDyIpzjvZMYomLfNbgVXwb6lojt6cogfYy9BWX9mv6v5MUCBUqHvq6vRc0vp9XVbZYB7rOfbLw5Nz5/dvR875yfmb0cvDc+DUhczjvD48O3ROnfPRW+cIpK+jk5dA4E7Xs2mxn9dzaUXTruTSYuyFsoJzViOaShq7s61Qcqpkm3nOwO/zeYfeBjuqWFpuwVsm8dKfg3zfIhNPUYYL/xy2I/reSrjIn4MktYDh3j5+h68h/syugsl1BPL/EC0hU9UAIjSKhuIGNyrpWqzUX22G2tLT0StYOQIUICzaha5Y6I3jO3XmZcMw9fa2aU4HO/l0WkesPlUMKAZ30xWr2wBkydvWoL+Lwn4PJxgfDHMw5ZTTSzHlO097FglWqVJWNezDmhXIXhY8n1ah9IShR8St2NN18OhKSCVM7hfHe6M9Lo6Ut9peQ7h6JKk0AIzEhkfOUp2W1KBrqQw3no/bxF+GLJqj7IUbrwlpqiZJO6S7apaPhbovFHAr4NPrNt3cwh6EVQwTW9moZZjZCCQURIg+aLYG9HuQ0dAH4f4fY7RUTwI/rDGZKn/uURIw0PJAJM58Z5kE0SRY+qEDml4KvJot/K4zCn1YtuThZ9ALlyyBcTqaD8dhVJ0cGWk8TpgD2u0Uqgaps0pXVAaUQ2XOVmFIchuf9HOQX6L5d36iWADRYFhfAtnjbZxMq0uQMVWurK0An8wQUZRNPYbGWb72qCyBAhzFCzKIS3Cb1Xwrhgw15Siadhld+YSkfGQdwo2h+8tP/8tt1sIRHzFo8KloS8yB3pRm6Uz9G8Yxz5TLSFDloHTnLAMJ898MZYP8QVloKXzEZK1lSRInrXxk7iEgxgpYLIGXOhHia0pIO18BunTdsjjHN816gZFszYK9KNupJdeAQ6yspnygj7G9bkhoSac9B/tlAhrxlAbGf0+ZsTN4ga7zAvamj9snCRYsSGKH5EvbcKv9R3XSI7ru4VnT9XiFUz6LA2cZp+nDv9wAaUFIE0kIYEQoZkOLbd2w93yVZXEk8Y3ztyOqaRAQQr3FAmlggWBETtFdzMl7tWfHn2TBDTPcQiBn8OcW7xDJXNIC0Lc1ucZNNFklKTKJK4B44LZVin6X8w3kwbksS0ZffRty0y3XCjsOves4Nz7Mzxh5HW1BVG41uk5uzDFqKEKdnCAeuuO5ghzUlDfDQjwYgOuQsubQKhqSF8VBF56NIXMYaQUFoLA2eZu0QLJXG3t9Vs1dQYDaVj3HODXCrzkS1KroXM7O0Jgm/MdoQ1+TElelMgZb5X6lDVgpAgjIHOXcD/f2SYQcm5FNVPIzh3EahsvgA17iNkO7KeNefHVnfwpWhm14ciYfzXywn0atNOREmZ+thLqkyHmSLqyVdl+8ON473nMr0MvopgbbNPUS154vu8duYFTmhpOzCWATx8B/oFgwQX3Q5BV1rEHYlbBKmewKmAt3Lp8SuTpOvBLoE0Q3Dz+HwTRuyvts0Q/4US40XgXh1AMpLPJWQUs1k2cRXzQbNec7QCHfNJl2yr2e6j6G9qpwVtDhga57FbujOwY9suX+9owm7q9cpMKLMdqqDxTs787iySpFQVtdVOV9uRWcBGuHSlMF8dGnvrHHXG7J+3iVWUNKpn56NY79ZNoq2TerQ1ksjvSqkBdUV8ql/RlI/63Bbg8WjaMfVeNtwNgD0MwyZfSg6ntsGojIOnP4glyP45i7SXVkBhQoo/iFi7qFe4mGzfcikKwjY8Y6SnjYBwMKQGAQfkT0wWeGo6JvoCsYJfmvNQsJ+2EVJNKrDPQI1gWtjdRzHtI5dL+LJw//zOVxYHuo5i2ClCRzYnDsjk1W6BkE/gbsjhRNIFgHJhYWHWzVSKG3fhIBi2u5h8g3Y3RAAc/LkGmJktY4Cj0gSzwklFUFMto8ti2HhsOxn1h97dxTIpw7O2YomqhZ6Sa/d2sqlM2NZXFMrWQzYwlHzlwN0lpvktHm0OCcd2TNE37UnQpTlh0s3ZpVgPbF4bOjwXGF9ar/WOAwLKYpbGo4pRDESkA+3z96evzcrZVpN4FNc0BH/o3FZ3ssqbbbsdHyks8VVMjpKotTrfgSH06ytFT6JEIxRwp9RYWAnsfJfanGy/gGtFBQ13JncFFrEd8wfFfu53cgED/8OcHAULXCFTzWO7lUiQKnYiYpNuQxmLauv1wyYLqtXEbS4aJ6Ch5oVQ6zlR8GP9rGI5iUbuxzuK90spgiLYWmDkynp5CMLEgmqgrhCJqo2KAVKmyFjLROsVWR0La72lUN6xiL27BW09WCKWAKFia1LGZDjLptVFCJJH+Sk8k7uYOQVHF49iw7m9eSluIyF8wNOO6lfe63GgigzxT5UzEu9/d3m9izNRCVKPKLSqZ9WUUsmwC7X61s9+mtxUSjgeie+4Eq00sXJ7DKHK6BRbTfqkCovpT699biU/3czdzvYF+jmPFeHKb4UKLY+8eHg+cjK+Lv11JswzHS7xmqogwzz6CcVSooR53zwhvEyymiGJ9vq2iyNpq9PqB8EjI/aRAFLMF/bDTwFfOnLFGDG4u4RtD31c6T3OCh0A7Rf2luqbRF1bujwHIhpOxV+bWodsmn9fwbQh+KYH90mBwyMBm3aY+LUTvXvFqi/41CY+RYt3V5TLqNsCtVxwA1ULc4it4pyhijrTI/CNesi6xaeN8tHt6+3cPLTyE1oun2NWoQQfSskX9RW4UsESHbRh+VqNBfH8RgSMiAF3x2G2AFL9h0vPt147UjgmEZsNIXIhAGMRO7WRNP3e8CosbJw8/LYOpj/Oo0SJdxFIyDEB6AYA09gZaWTPAMVuBrZis88RNMKF5KHM7r5nB54qXqn4PHaWMiQaUriERRilbeFjipCNUCkgtXytTuZUnafRvRaFMni2H5tFr4JPRWUWCt+AqjeZcPf06lPitqwcM4q6w1WtBpxDQgzVqrB9MPSm1lzXNWWTWKPVHb1iPXj5wf6TSdWg2YlBfPuPFGq2iEd3aclkpw2shmWLQC3EBdly+E7cQHES5aTZ1itbvzJJhidOQwcH7zG2ebTmqsFhH8/Hf4K82AIN0P3ShluTK2JwWRynMM2wYMHI+wK483XxhpYUi3PNSkr4gJ0l9QjaaPpJxGdE59FIHJEIEXVsRZ5MFhxSZFh0aOlbAKC2fF8dspYU+ZZDaRUPvrwrUVBkFuNC1GNgOBRniI5GEsORS+RCn0hsGISKFI8sfeYHmJZNHOQjme+yiu+LEy3LIibkgNCUbkmKDlS2AemXwQWS6KHo4e/jwN5jExaYzQbuV9CiLiUoRVu0mARauA86UP64GN7vJGOdzw4lihF9jjpRkeyVhXjKrFYc/ZaLtcks8YL8gNWuKoj42j4HRg6DVJiIJkp0uG8SNeCJp9SyUi7YuDQc8GXAA7MoGyFBxOg+W7f4ib+YLPKyhA9APDh5OAnNb5Mz5FRQmklD9kSLV0HGm0Qwo8k5FQOqeURL8Ro8Rpl74yyS8VTuIe+dnDzyjYi+O4sN8wdAb98qHDYNvdxCkFy6MsrfFK1PjjSGN/2EGJ7YlydVGnzJBYDZOLtEC3q6wcogtJN074SBI+ClNrFIfq6bz9prpjoT/KkML9Cv2xHFi/024G/VegPd34ioRiDiBiOQ54PINBhQXnM41CQTggCFezxgKQKL9GTzIPknD1kap6N9L6bXMxl/30okPDUW80aHXSW1Tju6qgOM3j9tfs/ozBHkyZ7rujTrGhYvtarR4ayEN3dCdQ+TXZpTU8ENkfllOu6xeWdYkLsP5Wn6Y8UZzGIBHn3E3iwtPGuFA2SBjhuXY5QzW43W0mM5DBetdEDrkZbFyYYiDLPBiJOH4uQWJkBQ/GL4JXwFeSk91GXDI/4qgxcDWSLySZ3sajn0luykEyWDS8yYF8nbCHf5JVtsqc2sqQ90XzxbhGmrwk3vPB4sks8eUp8PH1UgcOzCIiq0vSjPWXq20kB5SrbxKvbmzMguHqLwyGK1yGV37qZ5m0KrkqEK55/FgPhygDPQXaAbrHl+U3c5YpBi+FdDAKEDWImgh3BAgN6IoibpvHV7lurTCFQlQxA9hbe916l6WpIJiSWYPEI6A5l003VVMxrPkWpZhhF2eGmuF769IJUjJa8imZPTn7t8579f1BpzuYfXjSTRhsoglruR0c3B+BNuZPuvikoz75Iz7pbkRAxNFATYaUAxZ6tPqMa/JS0syxtiwhVKCuiOQoPOxWsaseiW8DEYzzJl6G7EZ4Ntvq+8r0Maako9cqUrDs7ffudp/1jPcyAcse5l/Z3evpbyvTrxBAILCneYYFo9vEH6vxMJqCeouhRMJZy6ViirYzBTbDfttIA91fq4HmB1laA5FpoQ6+12hln1z5FMyOh2NRsF9y7tJ1jnyQg1OUKJwveQRzPAa53CcXaVx5FHqdVfhZA+Dl6fO8gy+cs3jqLx/+BPT2Lj5AgIFkoyuU4jhAkZ6Amn8TUKRvgNa7dCEOcodkzItiPLSs0LE4Y1qcxK2IADMNHRZjsM0I0jaarvURmoW9IIp0aPhz6wFspYZVTs5nsa9K4ub5DzlczUex9pyHbaH2jVMmdrtTT7U7rS/et5qpgCelHqa5+qAHQ/rTqUe5flrX7D6PSqYzyCQboAgCY4C2dDplCKMITmlSpBSaG+5ks2i1k62j7IgdiI4KOx5a8baq1StxlBqJLVTFKOceBUaJdvBBnzMcIUkrJcWLXnX79xVHtQs35V0pPHqNT+lZbcaIbaOnWmUsX9ALWLRLSjSjR3iWtbUcYDWkul2uVOWgtYdSc+l7yvKw4QKdTFnc+dKlTCkKI1EKl6XwnpY0RimqyiYkjeNPfrYJu+hT1YG1asnYNqiCZwHAk8D+Er/EvKgdHgwNnseUuAkNPviduNR2VduUG4afCkl4OXvDN3GYgahAfhf+FQnhTlWzYxiTMeVT5sDTxE95PXs3IKrwlA+nY5RLizCZXTmTea0fZmv3/A+zYrvv5Zu9p231gb7Ji02gMl3RUDNqWFW4bytM0p+5uUgWHrqqFCRkwgYlcwWuVZzqMBweoJz+fuVHGberR7obiCAiRVEpU7K9C3jal6aOoK3KDzMrHU6VdenpRNhcCzttVUlpBVFMZ5+XJiq2p5mFmFXGKiGfWwK5ZCjMt4T/m2AsJbC6zbN2kY6XJ0+ABYYVX3/MDDqQma38W+uhrO+w9REetCrXTvwAJrkogUI9wfkBxnCDZ0oSZ7Vwoof/C1iFRzkzPC1mHg2AVUMwfuv0NuqBonuXQEGom4iBtBrc+F07D4AOyucELScEUQ/inEoomPq8rj2RlscCk0StSdHq2ZvYmUiSp+oKXVdGPwxv1QD9mgMUOsyaHvx5QPedqcLBPhZ8K1Lm6i4/RSb2AT3FCHHnhwrCVO5RUZP1tvhzszWDhJXbWwZTNRxAnM8U2nXr/fWBc2NsRDVBKy1SnprVdlhS+qxYRqlX0W+VB762oPNOMTcddXAdW3w9mVbKQxCmAHGGaz3ilFpAtbgIp6o+8amY0BodQi08vNLHRKdRG9lLZu4vP/339+rYPvzy0/+gQ6FFW6TfpiuK0ldwVVf6P9N5VGkeUM6i6pvFYv5X9b/CzhBNQM9Vwx+V9Wjm8Oa+gArLv/Q3Pqu1/EunnW76bzaEcz9EbcHu0wKy3DQMtjivpWrCPRPujY/PWgaqLA/OtnDviAD9r1PVu4O79UCwl7ZF6bAfsVL9kJ/RPCcSTxXpzrt+eh0vWYRPKPWUiH48x1SwAdpAfQeITBSEdIISi2X3S5ZiuljpUHW/7GJSci1ZrExTBf3VAlSi/zx7GyU4ytOdtyg1kn4EJ8XTw63Zk8Oxf+C857WIbrnpFWPk9/jabX94F70ip7WwdKV5WeDvRLyBRkIhGXI/1UrwaHte4omNDM2enMyjODGqpdfBcknVnpQEHVmGKEXqXlpICozsK0zx+S5CiQcbhqVpmRVxaE+crxz3XSQSa5klLg52DfJvpbrCP87ZOWgik3D18C+UBQAgaW81Ju2NaKadXuI4nciXQQdSfzDO7OchDwVH3Dg4UD9dUohjET9ig1MAYK9ktBw8pdSAqoijULl42djbDWUbeLp7bdM/Xm1TKZQLaLvk1Ma6lcHrv7pj9hG+2DoXbLVn9XHxUNXOVqsP9VnTWKlKL+uzGi/rrxct1TwGKT9wMzC0VKzY+tJrW4CWzstaf2UzPyNHZ3FqvUwxP5GbcbMgr0e75OTU4ZHimkP9tUxfOY7cFsl9RCYjOumaYeIiPPZGmYwoGyp6e4pkDgcNj+YzCkbCnYtTnD9otStA5a8btc41qYD73Hi9i95l25JFNUcKRCKpakH1tnHMo97xuM75KCWAxAkUHlGuX7ghdwa9u+1ez1Km0tm4zuFocTpaDVeFX8+Gn+vNWP3t4ryYfU8oh8i293qCk3BJuzjDYgZnrTFW5pvRHhK51oRZ1Fd3moWaFEZNQfo/mSXzoDrnZrEmVmtitSO0rB0XrD1vtMZwWHLUbQtJwlgXu82r0gjT1CCBW5hmUdBn8YTPWP6ssXlivYGBVhn5TvlVY729XhZdr6PrSq7iZhe6baDJmeuVWzX1yLMqNrU+qZOCBful0EykOhPm+VNQXSlTrvBSGwKB0G2P4xWg29d9VG2R3Sgylj73WYBScMs9fvhnYDJB6kzC4Ac8tIJh+QtVdua5FwKSuWGOigh+pm63rqtF/aqszpwXHrGkcD8U4X/GjhfxlLxJkv39eydW18SwHfthRsdGum7VyfxcOhbS17J0KK5qf+tCca+kzOQn1DdXZsoH390zNsfLphj5PFFzgREqCxCvnMVq6keYvQ1LsOpFsMdgq6txYNLdxec9VWILW7irnmZNQinHXAhXoCVpeU24hXpaxZCV1kckq8bXtQXRyGIrJZx5uTri/PK3/9kZVdqsgUPWtNI3So/viXUZURfabtAMea9ZCoIpZgpbot4lPBqAZIqHwHYGRxyN2rLEuim+vl7h6TPzuIvpLkcNKOAZyrBXCh9QGyl8jX1b/yVPY7vJ9Cj2bEw+Hgl79mPno189HxKtJnjHkpgQed+SdU4UPMxPt1xcdijRFxo9gcLEUXhf141tyvofO2V0G946vNGnZVA9LWunQe6yGsVQTk7NltPVe3qtmAvWWwp4kjIg1oZsWjz3NXnUtk41GNS3TdXjlqeQkRsvz3b18iBxaraFBRmTNg3zUoy8IRtObjcfNL86EwUUNQsgB6iBwYfP0XEwRwU8VukhXl/A6PSx4jolaSiMJ0LtNBypDfprfOS8YpDFbA0qAl921MWTDPaZccyj4Jlr4l8G7aZ1ijCY7cZ1Bmo/ZdVHXG2XR0LDyCvNIJIRkvaikEqZN7HUesJmCUuvvGJuy0Yx1X1sgcV2rwZ5UIKpXX2x2FQ2tZlIn0R8W6H+FahSzPNWLfrPnsiT2D4aVMi0khPDAxFGr+j/H5z/qNLSvISq4WMZspDKt4pV7cOTmjyNgiyV10vkC5Tzzz0nqX3N8iMV+mmKSu+4ii9ownEtYQQSv0zx3lh77Nq+MjonLhYnZ+XtT7Wgn4qeFYpSHTbb0FlLwCCWQTuC0nHCYBFkw/1euW2aZzpsdWmxFvgwhVLk1bLUWGzTCIl9MWQLsyfvFdsxNyu+LxvoPjypbiWVWcB4tJe1oECeC/oXg2lzA7e1OKpv0nDGIctxF1S6lM3iEMgPxszhXCqPDioRQ584+tza2hBF+XCtqK80X4/9cospFaqwq0SfLcajEPpGV6sAjQKvmwHAa5Ts14/onhragBqLtFPvFbg/FDegtWAUueqBv7qO6thvukHL95euh8l9xaIrw/5TaEEiDWeawjehRAoQ+CXfVg4u1TWW1PhNBA6VuDZuYbFz7EMphEg1QKO+ZO668Hhyjp5wPm0yhXmKF2PDUCwDf+m2q3Y2LrtITVKDrjaU5bUqUbYx2m4+fU2nsMLAYjNj2vl5nfIqrJy/lerhuZDJ/grtneWB11gOSsmVVUT9FEb4TYTGJoKjNaxW2nIYZYKXJELfv123cj8IV57Q06qunsA/HjMh9G5e0FpuFeSZKspug6pxY+NDp0ZVr56RXMJAg6yHkcpJ5IfcxUEBlu7x6PXpG4oFODl//e3h3yDe2STqnJgLaKptAx8FTQ5EDlgzaGy2hgaA4AEMbvi1TAklEA+mwxoIqshfg06K6V7XjT2sVDGTYy4wbiIXF51o2goFgOlBohVydDnB7K/ijTLICR8KzImZAl8z2gifgBYyus4T1eyMsm4U369OfW8Ca7PT7FTZdKpy4HsVoZYlCm1jSGWErHP4AHUk/5LiUTpwbijHODmRboJURA90nIW8CEgiWuIsdEdNpXXnMS4l7eYvng1f5DD2MrSdtbhutNtT73nRS/BkALzcdq+n8Ka/xEAx5PS4c5EY4KcZOIa8hS4EzijwapbQcVwXjwd0mqTkkO0f+3RxUH97l8IDZHfKjSR9ESRWDizbr4orG+zuWnN1SKAlraLmB7xnMZDfZ1MUkUW2LTms0yTgx+zyxB3ijGEWRAKSR+Xt+LWzdBV0lPCw/Yi0XDyc1/OzPPqK+IVMrfwpk0ZQdQmyR4snG1Wjv0BomgfQNp3GcoteYW183it/s1FeMNOBLPby5u5jLQO6+ybGTJj4HznDOaVSmCUevg/ze4QwyGMSrvCWSycubhECqXkJ9PHh5xsWdt16umSOw3qrRZPQd5GDvUFylSbp0NR87UUGfhARFpzUM/NKJQff+qHz8CcH4wrotAeU80sCxGdKkVafOqxYHFviMNogj8oa9gnynv0lMheZGVHenITfKeM5JsuhS5DwW+in2aPDkGWzr/htjHg9h+Qv8pXKYwS9l0BwQUQyn0ZRyAXc5/KbiD+mccDzh38Is2ARC5yl21n/tdI20iVWFP1rvVrhE4T6akxDS76f8wz5QE2FTy9l8vu18+4eZsFNXCQW4hciAL3nIUvPQ1Q6eKJaeo8rwa93Ezzhl5/+3m1/TKg23Sql5VUp50GRV8Ja045YI2D6AzMxnxbTnMXzOZB2Plp+KU85P9SnCiquOr6qUfBzxZaRk8KPvpcTwyGJdvKRtkphzPLCjA0CH43LQT77DZmczyeOxiFqr8mUiWo4e0EMp5tZ+QRzZM5vWSMV7UAiBMkthGrnb4+ORufnmzCZweapCPG68JrjiHIIYhs2HAS/7ohGwY3Un2kQRuouhUd/NunoI7N2KShUlbNrZ693t/PUzNn1KbJy1SW9MgWgBpHxm147pSXh0g5wfeI0TH95900jN8y9gLb4QormmsaJweqL8HwuQgnBCAUi3HuAgaTF5sPskG+WJBbLfaDy7VYDUah8ESi/AxSbrrlsmhe6rLodgWJJN438L98sq0f+F62qof/qdbJrr6ZRACvkxsfBhktN9hH3cLoIIq4T8qRA+SJzfYmMY5hCcVZz5R8aovmNf1wguqhoZcsayWeZmgIVc6sAgWyLlKvLulKRFeRXvzf80+TRUO8Q5+IKPIiT4Ec2bVXIJcW+anjB+GbpLEmifnF2+pKL1RfFuvHWLh+fbeLXkZr4veJWmalBOodiP/Jbxm26eaMzIn2rqNHk1m8KXS8swXRZqnZ/qjAHk8+JC7FDLvkcaDsFMOCaJWX97N4WVCeO9PNuku6MZZMrFFCCGSxsS1yVVbG4AjYQ1FagAq2yVsuNr10NwI7oov3I1a/qh9DA7CoXkRWKe5Vwxbj7hr61YFIBnYd8jjrO1GeLOOLWuy7NuGmT43fSgrIvFAZvGcOuU0FSzfell6ZgWFqG6yCaGuNY+vdhXNi/tOFj1GAU3/pBVj7gz0uMFsvs/qDqct36gdSQMqC1CCoxCD77JVqsDKK5Tli6UtG6twXfwf1NhmngR2TK0yp330XvItf5Sk5g7XgkjlPyISquDlW+5Xkr/Bs/CJGbubacyl48mwEF5zPZkjU7/MpdvSGhCqAIqzq86ubO6jgtTdpM3Kv7PR6yoqNWq9RHE7Dv3Ih77xbAvmAS6K46PHN8HgNNTOEjXAmTciu/Gq/dVXUd2y3MVqO2jWaVqVVVw0rJR7VumOD1ZeGks1gcuRIlCko5DHHrATHRF49nN2wLx0ApylQsFOU+cSlhspx5frEVYfKB815r9AmWAQL4BJOGuNZEJvnFhUEEExD6qPcWdxiaeV1YakUfzFviyu1BxS4OnvZ6l1tV5U7lmfROzgqBRDtXuWcC9yHFluIF48mNTxfLb2n5VPgM18MzomueC3QWW3+BWTV5Wigt35mv96FsDj+9vmdppG+Of4ytmF5c/8zTtBRZZhLHn8eJ/x/sGz1ZReY2VxFOea2jm9LYMonnAExaq9TLQkKzd8tbVT0Xb54uy2srOv7T3l1fy8udF4J/oI2xtKJ0HLFJSwUrLQIFtBVmgQKgGtuALJRbgPzgjlMwdZjdbveRWbv3NsnavVO67NQO5Ckfm7/waTv87MzY5AojVYA1jVmSxZRynOd7AAk/XvhZMOG/myXuVg7772AerO9XaRbM7qU9qsHJdXEROQzhtQAenigDwfS0Qxc4O8MgY3R/qi6s/DLyqsPMg4FemMtQ/Z6hvW0gk2JRRSKdxrcRcmcPkMEDYoOSvLL7mgqM/nIZorNeILnCprG/9qeWT6k7T0qpstNi1gtR9SNlVT0zKUp01HWjmeaip/cIgbOJ0GkTPAsAm2bQzGVOdUYPbKpox4GXFmlubRRnvRprokJFJCho3g1VV51s2+XdMRK/5Dew94Fc4IENnQhKRg4tPm4eLTO4mHXk1tt4BuVeDf0VkCK+wB6P4GhhmxzfF7MLV4g7pdwgGsI0X4zauL1KcDWeVJ/NotnqV2JAcywo3DvN8v+s3VZ1ZYzwDi5/bx6mUlbdXvoYJHDlO1mM91jweyuAIqL9kPFLLDZQSLqbJkZ79J3C+b31g15lWENFYjirnFDk9C9L7+6nvZG46EroBE0vI+6tv4x4IC4AqRvfaR5tA+sazIBekcyT8mVGWdUQfBwfJyOYBCAtOFxrzfzF+OFPIoxn5v9IuamLBrkgDxwb0K1KbDIHrAtKmiD1dL9XlyrcHHF+zb26pARXYtgfuO5gRvNUKrmPSaba3ytywNZmSq1wZjZEJWx0lVA2kgMHzw9OQGXEOKobny5njimtxPnvDr8e7O45uOkpIyNmbJF4HnedU+Bj0YSyvfB7bQg7ZjBHDp0zSnnyM87lMCoDL7LEpYaO0tUYFjDDhJfx+jUXe6hm0fd7vQ2zxuNUa0lhinv8TFJpzd2K5mI/LWVv5VmIEhYWCbyhcX8V4sSzCLnj0O1CJ+5m9nst/yu/hdD9ktppX6J9kTJEYSH0uEDnMfTtybxzVOzjM8SKGeKHc3CeLNlhbeass3w2nLm8JXqGg3BSmC68QejgXfQeG1MNHh+Z1lSPqdiCQXvkTPE8kpM8D/hT5HlCVDpc4qlMfBTGMZp9/j/oZlcX'
        new_source = _zlib.decompress(_b64.b64decode(payload))
        app_path.write_bytes(new_source)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception:
        # Se o bootstrap falhar, o atualizador normal continua disponível.
        return

_bootstrap_v052_app()