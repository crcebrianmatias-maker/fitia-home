
import os, sqlite3, hashlib, secrets, base64, mimetypes, json
from datetime import datetime
from pathlib import Path
from functools import wraps
import requests
from flask import Flask, request, jsonify, session, render_template, send_file, abort

BASE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("FITIA_DATA_DIR", str(BASE)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB = DATA_DIR / "fitia.db"
UPLOADS = DATA_DIR / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FITIA_SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

ROUTINES = [
 {"title":"Pecho + Tríceps + Core","mins":38,"ex":[
  {"name":"Flexiones","sets":3,"reps":"8-15","weight":0,"rest":60,"group":"Pecho","demo":"pushup"},
  {"name":"Press de pecho con mancuernas en el piso","sets":4,"reps":"10-12","weight":5,"rest":60,"group":"Pecho","demo":"press"},
  {"name":"Press cerrado con mancuernas","sets":3,"reps":"10-12","weight":5,"rest":60,"group":"Tríceps","demo":"press"},
  {"name":"Extensión de tríceps sobre cabeza","sets":3,"reps":"10-14","weight":2.5,"rest":50,"group":"Tríceps","demo":"triceps"},
  {"name":"Plancha","sets":3,"reps":"30-45 s","weight":0,"rest":45,"group":"Core","demo":"plank"},
  {"name":"Dead bug","sets":3,"reps":"8-10/lado","weight":0,"rest":45,"group":"Core","demo":"deadbug"}]},
 {"title":"Piernas + Glúteos + Abdomen","mins":42,"ex":[
  {"name":"Sentadilla con barra","sets":4,"reps":"10-12","weight":10,"rest":75,"group":"Piernas","demo":"squat"},
  {"name":"Peso muerto rumano con barra","sets":4,"reps":"10-12","weight":10,"rest":75,"group":"Piernas","demo":"hinge"},
  {"name":"Estocadas con mancuernas","sets":3,"reps":"8-10/lado","weight":5,"rest":60,"group":"Piernas","demo":"lunge"},
  {"name":"Puente de glúteos con barra","sets":4,"reps":"12-15","weight":10,"rest":60,"group":"Glúteos","demo":"bridge"},
  {"name":"Elevación de talones","sets":4,"reps":"15-20","weight":0,"rest":40,"group":"Gemelos","demo":"calf"},
  {"name":"Crunch controlado","sets":3,"reps":"15-20","weight":0,"rest":40,"group":"Abdomen","demo":"crunch"}]},
 {"title":"Espalda + Bíceps + Funcional","mins":40,"ex":[
  {"name":"Remo inclinado con barra","sets":4,"reps":"10-12","weight":10,"rest":70,"group":"Espalda","demo":"row"},
  {"name":"Remo a una mano con mancuerna","sets":3,"reps":"10-12/lado","weight":2.5,"rest":55,"group":"Espalda","demo":"row"},
  {"name":"Curl de bíceps con barra","sets":4,"reps":"10-12","weight":10,"rest":55,"group":"Bíceps","demo":"curl"},
  {"name":"Curl martillo","sets":3,"reps":"10-14","weight":5,"rest":50,"group":"Bíceps","demo":"curl"},
  {"name":"Mountain climbers","sets":4,"reps":"30 s","weight":0,"rest":30,"group":"Funcional","demo":"climber"},
  {"name":"Farmer walk","sets":4,"reps":"40 s","weight":5,"rest":40,"group":"Core","demo":"walk"}]}
]

def db():
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row; return con

def init_db():
    con=db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,salt TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS profiles(user_id INTEGER PRIMARY KEY,age INTEGER,height REAL,goal TEXT,days_per_week INTEGER DEFAULT 3,minutes_per_session INTEGER DEFAULT 40,limitations TEXT,equipment TEXT,cycle_start TEXT);
    CREATE TABLE IF NOT EXISTS measurements(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,date TEXT NOT NULL,weight REAL,waist REAL,abdomen REAL,chest REAL,biceps REAL,leg REAL);
    CREATE TABLE IF NOT EXISTS workouts(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,date TEXT NOT NULL,routine_index INTEGER NOT NULL,title TEXT NOT NULL,duration_minutes INTEGER,cycle_week INTEGER);
    CREATE TABLE IF NOT EXISTS set_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,workout_id INTEGER NOT NULL,exercise_name TEXT NOT NULL,set_no INTEGER NOT NULL,reps TEXT,weight REAL,effort INTEGER);
    CREATE TABLE IF NOT EXISTS photos(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,date TEXT NOT NULL,file_path TEXT NOT NULL,view_type TEXT DEFAULT 'general',ai_analysis TEXT);
    CREATE TABLE IF NOT EXISTS coach_notes(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,date TEXT NOT NULL,request TEXT,response TEXT);
    """)
    con.commit(); con.close()

def hash_pw(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),220000).hex(),salt

def login_required(fn):
    @wraps(fn)
    def w(*a,**k):
        if not session.get("uid"): return jsonify({"error":"No autenticado"}),401
        return fn(*a,**k)
    return w

@app.route("/")
def index(): return render_template("index.html")

@app.get("/api/routines")
def routines(): return jsonify(ROUTINES)

@app.post("/api/register")
def register():
    d=request.get_json(force=True); name=(d.get("name") or "").strip(); email=(d.get("email") or "").strip().lower(); pw=d.get("password") or ""
    if not name or "@" not in email or len(pw)<6: return jsonify({"error":"Datos inválidos."}),400
    h,s=hash_pw(pw)
    try:
        con=db(); cur=con.execute("INSERT INTO users(name,email,password_hash,salt,created_at) VALUES(?,?,?,?,?)",(name,email,h,s,datetime.utcnow().isoformat()))
        uid=cur.lastrowid
        con.execute("INSERT INTO profiles(user_id,age,height,goal,days_per_week,minutes_per_session,limitations,equipment,cycle_start) VALUES(?,?,?,?,?,?,?,?,?)",
                    (uid,44,190,"Reducir grasa y ganar músculo",3,40,"","2 mancuernas: 2,5 kg por lado; barra: 5 kg por lado",datetime.utcnow().date().isoformat()))
        con.commit(); con.close(); session["uid"]=uid; return jsonify({"ok":True})
    except sqlite3.IntegrityError: return jsonify({"error":"Ese email ya existe."}),409

@app.post("/api/login")
def login():
    d=request.get_json(force=True); con=db(); u=con.execute("SELECT * FROM users WHERE email=?",(d.get("email","").strip().lower(),)).fetchone(); con.close()
    if not u: return jsonify({"error":"Credenciales incorrectas."}),401
    h,_=hash_pw(d.get("password",""),u["salt"])
    if not secrets.compare_digest(h,u["password_hash"]): return jsonify({"error":"Credenciales incorrectas."}),401
    session["uid"]=u["id"]; return jsonify({"ok":True})

@app.post("/api/logout")
def logout(): session.clear(); return jsonify({"ok":True})

@app.get("/api/me")
@login_required
def me():
    con=db(); u=con.execute("SELECT id,name,email FROM users WHERE id=?",(session["uid"],)).fetchone(); p=con.execute("SELECT * FROM profiles WHERE user_id=?",(session["uid"],)).fetchone(); con.close()
    return jsonify({"user":dict(u),"profile":dict(p)})

@app.post("/api/profile")
@login_required
def profile():
    d=request.get_json(force=True); con=db()
    con.execute("UPDATE profiles SET age=?,height=?,goal=?,days_per_week=?,minutes_per_session=?,limitations=?,equipment=? WHERE user_id=?",
                (d.get("age"),d.get("height"),d.get("goal"),d.get("days_per_week",3),d.get("minutes_per_session",40),d.get("limitations",""),d.get("equipment",""),session["uid"]))
    con.commit(); con.close(); return jsonify({"ok":True})

@app.route("/api/measurements",methods=["GET","POST"])
@login_required
def measurements():
    con=db()
    if request.method=="POST":
        d=request.get_json(force=True)
        con.execute("INSERT INTO measurements(user_id,date,weight,waist,abdomen,chest,biceps,leg) VALUES(?,?,?,?,?,?,?,?)",
                    (session["uid"],datetime.utcnow().isoformat(),d.get("weight"),d.get("waist"),d.get("abdomen"),d.get("chest"),d.get("biceps"),d.get("leg"))); con.commit()
    rows=con.execute("SELECT * FROM measurements WHERE user_id=? ORDER BY date",(session["uid"],)).fetchall(); con.close()
    return jsonify([dict(r) for r in rows])

def cycle_week(uid):
    con=db(); p=con.execute("SELECT cycle_start FROM profiles WHERE user_id=?",(uid,)).fetchone(); con.close()
    if not p or not p["cycle_start"]: return 1
    start=datetime.fromisoformat(p["cycle_start"]).date(); delta=(datetime.utcnow().date()-start).days
    return (delta//7)%4 + 1

@app.get("/api/cycle")
@login_required
def cycle():
    w=cycle_week(session["uid"])
    labels={1:("Adaptación","Volumen moderado y foco en técnica."),2:("Progresión","Sumar repeticiones o una serie si el esfuerzo lo permite."),3:("Intensidad","Buscar mejores cargas o variantes más exigentes."),4:("Consolidación","Mantener calidad, controlar fatiga y preparar el siguiente ciclo.")}
    return jsonify({"week":w,"name":labels[w][0],"description":labels[w][1]})

@app.post("/api/workouts")
@login_required
def workout_save():
    d=request.get_json(force=True); con=db(); cw=cycle_week(session["uid"])
    cur=con.execute("INSERT INTO workouts(user_id,date,routine_index,title,duration_minutes,cycle_week) VALUES(?,?,?,?,?,?)",
                    (session["uid"],datetime.utcnow().isoformat(),d["routine_index"],d["title"],d.get("duration_minutes"),cw))
    wid=cur.lastrowid
    for s in d.get("sets",[]): con.execute("INSERT INTO set_logs(workout_id,exercise_name,set_no,reps,weight,effort) VALUES(?,?,?,?,?,?)",(wid,s["exercise_name"],s["set_no"],str(s.get("reps","")),s.get("weight"),s.get("effort")))
    con.commit(); con.close(); return jsonify({"ok":True,"workout_id":wid})

@app.get("/api/last-sets/<path:exercise>")
@login_required
def last_sets(exercise):
    con=db(); rows=con.execute("""SELECT sl.reps,sl.weight,sl.effort,w.date FROM set_logs sl JOIN workouts w ON sl.workout_id=w.id
        WHERE w.user_id=? AND sl.exercise_name=? ORDER BY w.date DESC,sl.set_no ASC LIMIT 8""",(session["uid"],exercise)).fetchall(); con.close()
    return jsonify([dict(r) for r in rows])

@app.get("/api/progression")
@login_required
def progression():
    con=db(); rows=con.execute("""SELECT sl.exercise_name,sl.effort,sl.reps,sl.weight,w.date FROM set_logs sl JOIN workouts w ON sl.workout_id=w.id WHERE w.user_id=? ORDER BY w.date DESC,sl.id DESC LIMIT 150""",(session["uid"],)).fetchall(); con.close()
    grouped={}
    for r in rows: grouped.setdefault(r["exercise_name"],[]).append(dict(r))
    out=[]
    for name,logs in grouped.items():
        recent=logs[:4]; eff=[x["effort"] for x in recent if x["effort"]]; weights=[x["weight"] for x in recent if x["weight"] is not None]
        if not eff: continue
        avg=sum(eff)/len(eff); cur=max(weights) if weights else 0
        if avg<=2: advice="Subí 1-2 repeticiones por serie; si ya estás arriba del rango, aumentá peso."; sw=round(cur+2.5,1) if cur else 0
        elif avg>=4.5: advice="Mantené o bajá volumen hasta recuperar margen."; sw=cur
        else: advice="Mantené peso y buscá una repetición extra."; sw=cur
        out.append({"exercise":name,"avg_effort":round(avg,1),"advice":advice,"suggested_weight":sw})
    return jsonify(out[:15])

@app.route("/api/photos",methods=["GET","POST"])
@login_required
def photos():
    con=db()
    if request.method=="POST":
        f=request.files.get("photo"); vt=request.form.get("view_type","general")
        if not f or not f.filename: return jsonify({"error":"Falta foto"}),400
        ext=Path(f.filename).suffix.lower()
        if ext not in [".jpg",".jpeg",".png",".webp"]: return jsonify({"error":"Formato no permitido"}),400
        userdir=UPLOADS/str(session["uid"]); userdir.mkdir(exist_ok=True); path=userdir/(secrets.token_hex(18)+ext); f.save(path)
        cur=con.execute("INSERT INTO photos(user_id,date,file_path,view_type) VALUES(?,?,?,?)",(session["uid"],datetime.utcnow().isoformat(),str(path),vt)); con.commit(); pid=cur.lastrowid; con.close()
        return jsonify({"ok":True,"id":pid})
    rows=con.execute("SELECT id,date,view_type,ai_analysis FROM photos WHERE user_id=? ORDER BY date DESC",(session["uid"],)).fetchall(); con.close()
    return jsonify([dict(r)|{"url":f"/api/photos/{r['id']}/file"} for r in rows])

@app.get("/api/photos/<int:pid>/file")
@login_required
def photo_file(pid):
    con=db(); r=con.execute("SELECT * FROM photos WHERE id=? AND user_id=?",(pid,session["uid"])).fetchone(); con.close()
    if not r: abort(404)
    return send_file(r["file_path"])

@app.post("/api/photos/<int:pid>/analyze")
@login_required
def analyze_photo(pid):
    con=db(); r=con.execute("SELECT * FROM photos WHERE id=? AND user_id=?",(pid,session["uid"])).fetchone()
    p=con.execute("SELECT * FROM profiles WHERE user_id=?",(session["uid"],)).fetchone()
    m=con.execute("SELECT * FROM measurements WHERE user_id=? ORDER BY date DESC LIMIT 1",(session["uid"],)).fetchone()
    if not r: con.close(); return jsonify({"error":"No encontrada"}),404
    api_key=os.environ.get("OPENAI_API_KEY")
    if not api_key:
        text="Foto guardada. Para comparar evolución, usá misma postura, luz y distancia junto con peso, cintura y rendimiento."
    else:
        path=Path(r["file_path"]); mime=mimetypes.guess_type(path.name)[0] or "image/jpeg"; b64=base64.b64encode(path.read_bytes()).decode()
        prompt=f"""Asistente de entrenamiento. Foto para seguimiento deportivo general.
Perfil: {json.dumps(dict(p),ensure_ascii=False)}
Última medición: {json.dumps(dict(m) if m else {},ensure_ascii=False)}
Describí postura visible, simetría aparente y grupos a priorizar. No diagnostiques ni estimes porcentaje exacto de grasa. No prometas reducción localizada. Cerrá con 3 recomendaciones de entrenamiento."""
        payload={"model":os.environ.get("OPENAI_MODEL","gpt-5.6-luna"),"input":[{"role":"user","content":[{"type":"input_text","text":prompt},{"type":"input_image","image_url":f"data:{mime};base64,{b64}","detail":"auto"}]}]}
        try:
            resp=requests.post("https://api.openai.com/v1/responses",headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},json=payload,timeout=60); resp.raise_for_status()
            obj=resp.json(); text=obj.get("output_text") or "Análisis no disponible."
        except Exception: text="No se pudo completar el análisis remoto."
    con.execute("UPDATE photos SET ai_analysis=? WHERE id=?",(text,pid)); con.commit(); con.close(); return jsonify({"analysis":text})

@app.delete("/api/photos/<int:pid>")
@login_required
def delete_photo(pid):
    con=db(); r=con.execute("SELECT * FROM photos WHERE id=? AND user_id=?",(pid,session["uid"])).fetchone()
    if not r: con.close(); return jsonify({"error":"No encontrado"}),404
    Path(r["file_path"]).unlink(missing_ok=True); con.execute("DELETE FROM photos WHERE id=?",(pid,)); con.commit(); con.close(); return jsonify({"ok":True})

@app.post("/api/coach")
@login_required
def coach():
    d=request.get_json(force=True); q=(d.get("message") or "").strip()
    con=db(); p=con.execute("SELECT * FROM profiles WHERE user_id=?",(session["uid"],)).fetchone(); m=con.execute("SELECT * FROM measurements WHERE user_id=? ORDER BY date DESC LIMIT 3",(session["uid"],)).fetchall()
    rows=con.execute("""SELECT sl.exercise_name,sl.effort,sl.weight,sl.reps,w.date FROM set_logs sl JOIN workouts w ON sl.workout_id=w.id WHERE w.user_id=? ORDER BY w.date DESC LIMIT 30""",(session["uid"],)).fetchall(); con.close()
    key=os.environ.get("OPENAI_API_KEY")
    if key:
        prompt=f"""Sos entrenador digital. Respondé en español argentino y de forma breve.
Objetivo/perfil: {json.dumps(dict(p),ensure_ascii=False)}
Últimas mediciones: {json.dumps([dict(x) for x in m],ensure_ascii=False)}
Últimos registros: {json.dumps([dict(x) for x in rows],ensure_ascii=False)}
Semana del ciclo: {cycle_week(session["uid"])}
Pregunta: {q}
Podés proponer cambios de volumen, repeticiones, descanso o prioridad muscular. No diagnostiques ni reemplaces atención médica."""
        payload={"model":os.environ.get("OPENAI_MODEL","gpt-5.6-luna"),"input":prompt}
        try:
            resp=requests.post("https://api.openai.com/v1/responses",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json=payload,timeout=60); resp.raise_for_status()
            ans=resp.json().get("output_text") or "No pude generar una respuesta."
        except Exception: ans="No pude conectar la IA. Puedo seguir usando recomendaciones locales."
    else:
        s=q.lower()
        if "20" in s and "min" in s: ans="Hacé una versión express: 4 ejercicios, 3 series, descansos de 30-45 segundos."
        elif "pecho" in s: ans="Podés priorizar pecho agregando una serie al press y otra variante de flexiones, sin repetir estímulo fuerte antes de 48 h."
        elif "cintura" in s or "grasa" in s: ans="La cintura baja con reducción de grasa general: fuerza, actividad aeróbica y alimentación consistente."
        else: ans="Puedo ajustar volumen, carga, descansos y grupos musculares. Conectá OPENAI_API_KEY para recomendaciones más personalizadas."
    con=db(); con.execute("INSERT INTO coach_notes(user_id,date,request,response) VALUES(?,?,?,?)",(session["uid"],datetime.utcnow().isoformat(),q,ans)); con.commit(); con.close()
    return jsonify({"answer":ans})

if __name__=="__main__":
    init_db(); app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=True)
