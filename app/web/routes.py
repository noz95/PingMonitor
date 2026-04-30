import threading
import time

from flask import Flask, jsonify, render_template, request

from app.db.database import get_db
from app.utils.config import get_settings, set_settings
from app.utils.logger import logger


def register_routes(app: Flask):

    # ── Page routes ──────────────────────────────────────────────────────────

    @app.route('/')
    def dashboard():
        return render_template('dashboard.html')

    @app.route('/probes')
    def probes_page():
        groups = [dict(r) for r in get_db().execute("SELECT id, name FROM groups ORDER BY name")]
        return render_template('probes.html', groups=groups)

    @app.route('/groups')
    def groups_page():
        return render_template('groups.html')

    @app.route('/settings')
    def settings_page():
        s = get_settings()
        s['smtp_password'] = '••••••••' if s.get('smtp_password') else ''
        return render_template('settings.html', settings=s)

    @app.route('/network-scan')
    def network_scan_page():
        return render_template('network_scan.html')

    # ── API: stats ────────────────────────────────────────────────────────────

    @app.route('/api/stats')
    def api_stats():
        db = get_db()
        rows = db.execute("SELECT status FROM probes WHERE enabled=1").fetchall()
        counts = {'up': 0, 'down': 0, 'unknown': 0}
        for r in rows:
            s = r['status']
            counts[s if s in counts else 'unknown'] += 1
        avg = db.execute(
            "SELECT AVG(last_latency) avg FROM probes WHERE enabled=1 AND status='up'"
        ).fetchone()
        return jsonify({
            'total': len(rows),
            'up': counts['up'],
            'down': counts['down'],
            'unknown': counts['unknown'],
            'avg_latency': round(avg['avg'], 2) if avg and avg['avg'] else None,
        })

    # ── API: probes ───────────────────────────────────────────────────────────

    @app.route('/api/probes', methods=['GET'])
    def api_probes():
        rows = get_db().execute("""
            SELECT p.*, g.name group_name
            FROM probes p LEFT JOIN groups g ON p.group_id=g.id
            ORDER BY p.name
        """).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/probes', methods=['POST'])
    def api_create_probe():
        d = request.json or {}
        if not all(k in d for k in ('name', 'host', 'type')):
            return jsonify({'error': 'name, host, type requis'}), 400
        if d['type'] not in ('ping', 'http', 'https'):
            return jsonify({'error': 'type invalide'}), 400
        db = get_db()
        cur = db.execute(
            "INSERT INTO probes(name,host,type,group_id,interval,timeout,failure_threshold) "
            "VALUES (?,?,?,?,?,?,?)",
            (d['name'], d['host'], d['type'], d.get('group_id'),
             int(d.get('interval', 60)), int(d.get('timeout', 5)),
             int(d.get('failure_threshold', 3))),
        )
        db.commit()
        return jsonify({'id': cur.lastrowid}), 201

    @app.route('/api/probes/<int:pid>', methods=['GET'])
    def api_get_probe(pid):
        row = get_db().execute("SELECT * FROM probes WHERE id=?", (pid,)).fetchone()
        return (jsonify(dict(row)) if row else (jsonify({'error': 'not found'}), 404))

    @app.route('/api/probes/<int:pid>', methods=['PUT'])
    def api_update_probe(pid):
        d = request.json or {}
        allowed = ('name', 'host', 'type', 'group_id', 'interval', 'timeout',
                   'failure_threshold', 'enabled')
        fields = [f'{k}=?' for k in allowed if k in d]
        vals = [d[k] for k in allowed if k in d]
        if not fields:
            return jsonify({'error': 'rien à modifier'}), 400
        db = get_db()
        db.execute(f"UPDATE probes SET {', '.join(fields)} WHERE id=?", [*vals, pid])
        db.commit()
        return jsonify({'ok': True})

    @app.route('/api/probes/<int:pid>', methods=['DELETE'])
    def api_delete_probe(pid):
        db = get_db()
        db.execute("DELETE FROM probes WHERE id=?", (pid,))
        db.commit()
        return jsonify({'ok': True})

    @app.route('/api/probes/<int:pid>/history')
    def api_probe_history(pid):
        hours = int(request.args.get('hours', 24))
        rows = get_db().execute(
            "SELECT timestamp, status, latency FROM probe_results "
            "WHERE probe_id=? AND timestamp >= datetime('now', ?) "
            "ORDER BY timestamp ASC",
            (pid, f'-{hours} hours'),
        ).fetchall()
        labels = [r['timestamp'] for r in rows]
        latencies = [r['latency'] for r in rows]
        statuses = [r['status'] for r in rows]
        total = len(rows)
        up_pct = round(sum(1 for s in statuses if s == 'up') / total * 100, 1) if total else None
        return jsonify({'labels': labels, 'latencies': latencies,
                        'statuses': statuses, 'uptime_pct': up_pct})

    @app.route('/api/probes/<int:pid>/reset', methods=['POST'])
    def api_reset_probe(pid):
        db = get_db()
        db.execute(
            "UPDATE probes SET status='unknown', consecutive_failures=0, last_check=NULL WHERE id=?",
            (pid,),
        )
        db.commit()
        return jsonify({'ok': True})

    @app.route('/api/probes/bulk', methods=['POST'])
    def api_bulk_probes():
        d = request.json or {}
        ids = d.get('ids', [])
        action = d.get('action', '')
        if not ids or not isinstance(ids, list):
            return jsonify({'error': 'ids requis'}), 400
        db = get_db()
        ph = ','.join('?' * len(ids))
        if action == 'delete':
            db.execute(f"DELETE FROM probes WHERE id IN ({ph})", ids)
        elif action == 'enable':
            db.execute(f"UPDATE probes SET enabled=1 WHERE id IN ({ph})", ids)
        elif action == 'disable':
            db.execute(f"UPDATE probes SET enabled=0 WHERE id IN ({ph})", ids)
        elif action == 'assign_group':
            group_id = d.get('group_id') or None
            db.execute(f"UPDATE probes SET group_id=? WHERE id IN ({ph})", [group_id, *ids])
        elif action == 'update':
            fields, vals = [], []
            for k in ('interval', 'timeout', 'failure_threshold'):
                if d.get(k) is not None:
                    fields.append(f'{k}=?')
                    vals.append(int(d[k]))
            if not fields:
                return jsonify({'error': 'rien à modifier'}), 400
            db.execute(f"UPDATE probes SET {', '.join(fields)} WHERE id IN ({ph})", [*vals, *ids])
        else:
            return jsonify({'error': 'action invalide'}), 400
        db.commit()
        return jsonify({'ok': True, 'affected': len(ids)})

    # ── API: groups ───────────────────────────────────────────────────────────

    @app.route('/api/groups', methods=['GET'])
    def api_groups():
        rows = get_db().execute("""
            SELECT g.*,
                   COUNT(p.id) probe_count,
                   SUM(CASE WHEN p.status='up'   THEN 1 ELSE 0 END) up_count,
                   SUM(CASE WHEN p.status='down' THEN 1 ELSE 0 END) down_count
            FROM groups g
            LEFT JOIN probes p ON p.group_id=g.id AND p.enabled=1
            GROUP BY g.id ORDER BY g.name
        """).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/groups', methods=['POST'])
    def api_create_group():
        d = request.json or {}
        if not d.get('name'):
            return jsonify({'error': 'name requis'}), 400
        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO groups(name, description) VALUES (?,?)",
                (d['name'], d.get('description', '')),
            )
            db.commit()
            return jsonify({'id': cur.lastrowid}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    @app.route('/api/groups/<int:gid>', methods=['PUT'])
    def api_update_group(gid):
        d = request.json or {}
        db = get_db()
        db.execute("UPDATE groups SET name=?, description=? WHERE id=?",
                   (d['name'], d.get('description', ''), gid))
        db.commit()
        return jsonify({'ok': True})

    @app.route('/api/groups/<int:gid>', methods=['DELETE'])
    def api_delete_group(gid):
        db = get_db()
        db.execute("DELETE FROM groups WHERE id=?", (gid,))
        db.commit()
        return jsonify({'ok': True})

    # ── API: settings ─────────────────────────────────────────────────────────

    @app.route('/api/settings', methods=['GET'])
    def api_settings():
        s = get_settings()
        s.pop('smtp_password', None)
        return jsonify(s)

    @app.route('/api/settings', methods=['POST'])
    def api_save_settings():
        d = request.json or {}
        allowed = ('smtp_host', 'smtp_port', 'smtp_user', 'smtp_password',
                   'smtp_from', 'smtp_to', 'alert_enabled', 'retention_days')
        to_save = {}
        for k in allowed:
            if k in d:
                if k == 'smtp_password' and '•' in str(d[k]):
                    continue
                to_save[k] = d[k]
        set_settings(to_save)
        return jsonify({'ok': True})

    @app.route('/api/settings/test-email', methods=['POST'])
    def api_test_email():
        from app.core.alerts import send_test
        cfg = get_settings()
        send_test(cfg)
        return jsonify({'ok': True})

    # ── API: network scan ─────────────────────────────────────────────────────

    _scan: dict = {'running': False, 'results': [], 'started_at': None, 'finished_at': None}
    _scan_lock = threading.Lock()

    @app.route('/api/scan/status')
    def api_scan_status():
        return jsonify(_scan)

    @app.route('/api/scan/start', methods=['POST'])
    def api_scan_start():
        with _scan_lock:
            if _scan['running']:
                return jsonify({'error': 'scan déjà en cours'}), 409
            _scan.update(running=True, results=[], started_at=time.strftime('%Y-%m-%d %H:%M:%S'),
                         finished_at=None)

        def do():
            from app.core.scanner import full_scan
            try:
                r = full_scan()
                with _scan_lock:
                    _scan['results'] = r
            except Exception as e:
                logger.error(f'Scan error: {e}')
            finally:
                with _scan_lock:
                    _scan.update(running=False, finished_at=time.strftime('%Y-%m-%d %H:%M:%S'))

        threading.Thread(target=do, daemon=True).start()
        return jsonify({'ok': True})

    @app.route('/api/scan/add', methods=['POST'])
    def api_scan_add():
        d = request.json or {}
        host = d.get('host', '')
        if not host:
            return jsonify({'error': 'host requis'}), 400
        db = get_db()
        cur = db.execute(
            "INSERT INTO probes(name, host, type, interval, timeout) VALUES (?,?,?,?,?)",
            (d.get('name') or host, host, d.get('type', 'ping'), 60, 5),
        )
        db.commit()
        return jsonify({'id': cur.lastrowid}), 201
