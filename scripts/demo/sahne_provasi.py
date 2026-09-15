import json, time, urllib.request, subprocess
API="http://127.0.0.1:8020"; C="1adb6a23-49bf-4548-a884-a6ced158511e"
U="22222222-2222-2222-2222-000000000004"
CEVAPLI=["Dairesel bekleme koşulu nedir?","Banker's Algorithm hangi deadlock stratejisine girer?",
"Deadlock oluşabilmesi için hangi dört koşulun sağlanması gerekir?","Deadlock oluşması için gereken dört koşul nedir?",
"Mutex ile semafor arasındaki fark nedir?","Round-robin zamanlamada quantum süresinin seçimi neyi etkiler?",
"Semafor nedir ve ne işe yarar?","Context switch ne zaman gerçekleşir?",
"Turnaround time ile waiting time arasındaki fark nedir?","Süreç ile thread arasındaki temel fark nedir?",
"fork() çağrısı ne döndürür?","Context switch maliyeti neden yüksek?"]
RET=["İtalya'nın başkenti neresidir?","Bugün İstanbul'da hava nasıl?",
"Bu dersin vize sınavı ne zaman yapılacak?","Bugünkü dolar kuru ne kadar?"]
def kota():
    return int(subprocess.run(["psql","-d","dou_demo","-Atc",
      "select coalesce(sum(coalesce(charged_tokens,reserved_tokens)),0) from ai_token_reservations "
      "where user_id='%s' and created_at >= date_trunc('day', now() at time zone 'Europe/Istanbul') at time zone 'Europe/Istanbul'"%U],
      capture_output=True,text=True).stdout.strip() or 0)
def sor(q):
    body=json.dumps({"question":q,"mode":"qa"}).encode()
    req=urllib.request.Request(f"{API}/courses/{C}/chat",data=body,
        headers={"Authorization":f"Bearer dev:{U}","Content-Type":"application/json"})
    t=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=150) as r: d=json.load(r); code=r.status
    except urllib.error.HTTPError as e:
        d=json.loads(e.read() or b"{}"); code=e.code
    except Exception as e:
        return ("AĞ-HATA",0,time.monotonic()-t,str(e)[:60])
    st=d.get("status") or (d.get("error") or {}).get("code","?")
    return (st,len(d.get("citations") or []),time.monotonic()-t,code)
onc=kota(); print(f"jeton ÖNCE: {onc}\n")
print("### KAYNAKLI CEVAP VERMESİ GEREKEN 12")
ok=0
for q in CEVAPLI:
    st,c,sn,code=sor(q); iyi = st=="answered" and c>0
    ok+=iyi; print(f"  {'✓' if iyi else '✗'} {st:20} atıf={c:<2} {sn:5.2f}sn  {q[:48]}")
print(f"\n### REDDETMESİ GEREKEN 4")
red=0
for q in RET:
    st,c,sn,code=sor(q); iyi = st in ("out_of_scope","insufficient_context")
    red+=iyi; print(f"  {'✓' if iyi else '✗'} {st:20} atıf={c:<2} {sn:5.2f}sn  {q[:48]}")
son=kota()
print(f"\n=== cevaplı {ok}/12 · ret {red}/4 · jeton SONRA {son} · FARK {son-onc} ===")
