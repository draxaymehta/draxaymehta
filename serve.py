#!/usr/bin/env python3
"""Static server with byte-range support for local video seeking."""
from __future__ import annotations

import os
import re
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from typing import Optional


class RangeRequestHandler(SimpleHTTPRequestHandler):
    range_start: int = 0
    range_end: Optional[int] = None

    def end_headers(self) -> None:
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):
        path = self.translate_path(self.path)
        self.range_start = 0
        self.range_end = None

        if not os.path.isfile(path):
            return super().send_head()

        ctype = self.guess_type(path)
        try:
            file_obj = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        size = os.fstat(file_obj.fileno()).st_size
        range_header = self.headers.get("Range")

        if range_header:
            match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if match:
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else size - 1
                end = min(end, size - 1)

                if start > end or start >= size:
                    self.send_error(416, "Requested Range Not Satisfiable")
                    file_obj.close()
                    return None

                self.range_start = start
                self.range_end = end
                length = end - start + 1

                self.send_response(206)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Content-Length", str(length))
                self.end_headers()
                file_obj.seek(start)
                return file_obj

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.end_headers()
        return file_obj

    def copyfile(self, source, outputfile):
        if self.range_end is not None:
            remaining = self.range_end - self.range_start + 1
            while remaining > 0:
                chunk = source.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                remaining -= len(chunk)
            return

        super().copyfile(source, outputfile)


if __name__ == "__main__":
    port = 8000
    server = ThreadingHTTPServer(("", port), RangeRequestHandler)
    print(f"Serving at http://localhost:{port} (range requests enabled)")
    server.serve_forever()
