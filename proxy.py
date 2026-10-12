#!/usr/bin/env python3
"""TLS-wrapped HTTP CONNECT proxy, restricted to local OpenSSH."""
import asyncio, os, ssl, logging, base64, hmac

HOST = os.environ.get('NEXA_HOST','127.0.0.1')
PORT = int(os.environ.get('NEXA_SSH_PORT','22'))
USER = os.environ.get('NEXA_PROXY_USER','')
PASS = os.environ.get('NEXA_PROXY_PASSWORD','')
LOG = logging.getLogger('nexa')

async def pipe(src, dst):
    try:
        while data := await src.read(32768):
            dst.write(data)
            await dst.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        try: dst.write_eof()
        except (OSError, AttributeError): pass

async def handler(reader, writer):
    upstream = None
    try:
        first = await asyncio.wait_for(reader.readline(), 12)
        if len(first)>4096: return
        headers = {}
        for _ in range(64):
            line = await asyncio.wait_for(reader.readline(), 12)
            if not line or line in (b'\r\n',b'\n'): break
            if len(line)>8192: return
            key,sep,value=line.decode('latin1').partition(':')
            if sep: headers[key.strip().lower()]=value.strip()
        else: return
        def response(code, extra=''):
            writer.write(f'HTTP/1.1 {code}\r\n{extra}Content-Length: 0\r\nConnection: close\r\n\r\n'.encode())
        parts=first.decode('latin1').strip().split()
        if len(parts)!=3 or parts[0].upper()!='CONNECT':
            response('405 Method Not Allowed'); await writer.drain(); return
        if parts[1].lower() not in ('127.0.0.1:22','localhost:22','ssh.internal:22'):
            response('403 Forbidden'); await writer.drain(); return
        auth=headers.get('proxy-authorization','')
        expected='Basic '+base64.b64encode(f'{USER}:{PASS}'.encode()).decode()
        if not USER or not PASS or not hmac.compare_digest(auth,expected):
            response('407 Proxy Authentication Required','Proxy-Authenticate: Basic realm="Nexa"\r\n')
            await writer.drain(); return
        upreader,upwriter=await asyncio.open_connection(HOST,PORT)
        upstream=upwriter
        writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n'); await writer.drain()
        a=asyncio.create_task(pipe(reader,upwriter))
        b=asyncio.create_task(pipe(upreader,writer))
        await asyncio.wait((a,b),return_when=asyncio.FIRST_COMPLETED)
        for t in (a,b): t.cancel()
        await asyncio.gather(a,b,return_exceptions=True)
    except (OSError, asyncio.TimeoutError, UnicodeError) as exc:
        LOG.debug('Client error: %s',exc)
    finally:
        if upstream:
            upstream.close()
            try: await upstream.wait_closed()
            except OSError: pass
        writer.close()
        try: await writer.wait_closed()
        except OSError: pass

async def main():
    logging.basicConfig(level=logging.INFO)
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain('/etc/nexa-ssh/fullchain.pem','/etc/nexa-ssh/privkey.pem')
    server=await asyncio.start_server(handler,'0.0.0.0',443,ssl=ctx,limit=16384)
    LOG.info('Nexa TLS CONNECT listening on 443')
    async with server: await server.serve_forever()

if __name__=='__main__': asyncio.run(main())
