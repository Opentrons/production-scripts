from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.agent.protocol_analysis.opentrons_path import resolve_opentrons_environment
from modules.agent.protocol_analysis.service import ProtocolAnalysisService


@pytest.mark.asyncio
async def test_analyze_csv_protocol_roundtrip(tmp_path: Path, monkeypatch) -> None:
    env = resolve_opentrons_environment()
    if not env.available:
        pytest.skip(env.detail)

    protocol = tmp_path / "protocol.py"
    protocol.write_text(
        '''
requirements = {"robotType": "OT-3", "apiLevel": "2.20"}

def add_parameters(parameters):
    parameters.add_csv_file(
        display_name="CSV File",
        variable_name="csv_file",
    )

def run(protocol):
    protocol.params.csv_file.contents
'''.strip(),
        encoding="utf-8",
    )
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("a,b,c\n1,2,3\n", encoding="utf-8")

    service = ProtocolAnalysisService()
    monkeypatch.setattr(
        "modules.agent.protocol_analysis.service.config.DOWNLOAD_DIR",
        str(tmp_path / "downloads"),
    )

    class FakeUpload:
        def __init__(self, path: Path):
            self.filename = path.name
            self._data = path.read_bytes()
            self._offset = 0

        async def read(self, size: int = -1) -> bytes:
            if self._offset >= len(self._data):
                return b""
            if size < 0:
                chunk = self._data[self._offset :]
                self._offset = len(self._data)
                return chunk
            chunk = self._data[self._offset : self._offset + size]
            self._offset += len(chunk)
            return chunk

    missing = await service.analyze(protocol_files=[FakeUpload(protocol)])
    assert missing.result == "parameter-value-required"
    assert any(item.get("variableName") == "csv_file" for item in missing.run_time_parameters)

    ok = await service.analyze(
        protocol_files=[FakeUpload(protocol)],
        csv_variable_names=["csv_file"],
        csv_files=[FakeUpload(csv_path)],
    )
    assert ok.result == "ok"
    assert ok.errors == []
    assert json.dumps(ok.analysis)
