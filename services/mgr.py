
from sources import *
import logging
import asyncio
log = logging.getLogger(__name__)
class Mgr:
    def __init__(self):
        self.srcs = {}
        import sources
        for n in dir(sources):
            if n.endswith('Webs'):
                try:
                    self.srcs[n] = getattr(sources, n)()
                except: pass
        log.info(f"Loaded {len(self.srcs)} srcs")
    def get(self, name):
        return self.srcs.get(name)
    async def search(self, q):
        res = []
        async def _s(n, s):
            try:
                r = await asyncio.wait_for(s.search(q), timeout=25)
                if r:
                    for x in r: x['src'] = n
                    return r
            except Exception:
                return []
            return []
        tasks = [_s(n, s) for n, s in self.srcs.items()]
        try:
            out = await asyncio.gather(*tasks)
            for l in out: res.extend(l)
        except Exception as e:
            log.error(f"Search err: {e}")
        return res
mgr = Mgr()
