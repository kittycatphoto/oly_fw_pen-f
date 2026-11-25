#!/usr/bin/env python3
# Copyright 2026 kittycatphoto (original contributions)
# SPDX-License-Identifier: Apache-2.0
"""Updater preflight for a built films package: the stock PEN-F 3101 updater, run natively (tools/penf_update_probe).

  python3 preflight.py --package generated/films-v1.2/install/DCOLYMP/E1229999.BIN \
                       --restore generated/films-v1.2/restore-stock/DCOLYMP/E1229999.BIN

Checks: SD mode accepts (result 0) and requests exactly one write per component, each carrying that component's
decoded bytes; USB check mode accepts with no writes; the native SD client and both service branches forward the
package unchanged; the restore package is accepted the same way. Writes are trapped: nothing is flashed, no camera
is contacted, no update file is written. Not covered: the camera's boot after the write (see gate.py, checks.py).
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'tools'))
from oly_container import parse  # noqa: E402
from penf_update_probe import update_probe  # noqa: E402
from penf_input_recovery_probe import sd_client, sd_service  # noqa: E402

DESTINATIONS = {0x100: '0x803a0000', 0x101: '0x41800000'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def accept(name, package):
    blocks = parse(package)
    expected = {DESTINATIONS[b.kind]: (len(b.header + b.payload + b.trailer), sha(b.header + b.payload + b.trailer))
                for b in blocks}
    rows = []
    sd, _ = update_probe(package, mode=0)
    writes = {w['destination']: (w['bytes'], w['input_sha256']) for w in sd['write_requests']}
    rows.append({'check': f'{name}: SD update accepted, one write per component with its decoded bytes',
                 'pass': sd['returned'] and sd['result'] == 0 and writes == expected
                 and len(sd['write_requests']) == len(blocks),
                 'components': [hex(b.kind) for b in blocks], 'instructions': sd['instructions']})
    usb, _ = update_probe(package, mode=2)
    rows.append({'check': f'{name}: USB check mode accepted, no writes',
                 'pass': usb['returned'] and usb['result'] == 0 and usb['write_requests'] == []})
    client, _ = sd_client(package)
    ok = bool(client['request']) and client['request']['data_sha256'] == sha(package)
    for active in (False, True):
        service, _ = sd_service(package, client['request'], active_task=active) if ok else ({'dispatch': None}, None)
        d = service['dispatch']
        ok = ok and bool(d) and d['mode'] == 0 and d['bytes'] == len(package) and d['data_sha256'] == sha(package)
    rows.append({'check': f'{name}: native SD client and both service branches forward the package unchanged',
                 'pass': ok})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--restore', type=Path)
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    package = a.package.read_bytes()
    rows = accept('install', package)
    if a.restore:
        rows += accept('restore', a.restore.read_bytes())
    report = {'package_sha256': sha(package), 'camera_access': False, 'flash_writes': 'trapped',
              'passed': all(r['pass'] for r in rows), 'checks': rows}
    text = json.dumps(report, indent=2)
    print(text)
    if a.out:
        a.out.write_text(text + '\n')
    sys.exit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
