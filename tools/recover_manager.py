"""Local operator recovery for the only manager. Run on the restaurant computer."""
from pathlib import Path
import sys,secrets
from datetime import datetime,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,auth_ui

if __name__=='__main__':
    app.initialize()
    print('JUPITER — LOCAL MANAGER RECOVERY\nRun only on the restaurant computer by its authorized operator.')
    name=input('Manager username: ').strip()
    with app.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        user=db.execute("SELECT id FROM users WHERE username=? AND role='manager'",(name,)).fetchone()
        if not user: raise SystemExit('Manager account not found.')
        raw=secrets.token_urlsafe(32); expiry=(datetime.now()+timedelta(minutes=15)).isoformat()
        db.execute('UPDATE password_resets SET used=? WHERE user_id=? AND used IS NULL',(app.now(),user['id']))
        db.execute('INSERT INTO password_resets(user_id,token_hash,expires,issued_by,created) VALUES (?,?,?,?,?)',(user['id'],auth_ui.digest(raw),expiry,'LOCAL OPERATOR',app.now()))
        db.execute('INSERT INTO audit(username,action,created) VALUES (?,?,?)',('LOCAL OPERATOR','ออกลิงก์กู้คืนผู้จัดการ '+name,app.now()))
    print('\nOpen this link on this computer. It expires in 15 minutes and can be used once:\nhttp://127.0.0.1:8765/reset-password?token='+raw)
    input('\nPress Enter to close...')
