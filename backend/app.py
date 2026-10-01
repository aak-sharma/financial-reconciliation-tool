from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import io
import json
from reconciliation_engine import ReconciliationEngine

app = Flask(__name__, template_folder='../frontend', static_folder='../frontend/static')
CORS(app)

# Initialize database
def init_db():
    conn = sqlite3.connect('reconciliation.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS gl_entries (
        id INTEGER PRIMARY KEY,
        date TEXT,
        account_code TEXT,
        description TEXT,
        debit REAL,
        credit REAL,
        reference TEXT,
        uploaded_at TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS bank_entries (
        id INTEGER PRIMARY KEY,
        date TEXT,
        amount REAL,
        description TEXT,
        reference TEXT,
        bank_reference TEXT,
        uploaded_at TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS reconciliation_matches (
        id INTEGER PRIMARY KEY,
        gl_entry_id INTEGER,
        bank_entry_id INTEGER,
        match_type TEXT,
        confidence_score REAL,
        reconciled_at TIMESTAMP,
        FOREIGN KEY(gl_entry_id) REFERENCES gl_entries(id),
        FOREIGN KEY(bank_entry_id) REFERENCES bank_entries(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS exceptions (
        id INTEGER PRIMARY KEY,
        entry_type TEXT,
        entry_id INTEGER,
        exception_type TEXT,
        description TEXT,
        amount REAL,
        created_at TIMESTAMP,
        status TEXT
    )''')
    
    conn.commit()
    conn.close()

init_db()
engine = ReconciliationEngine()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload-gl', methods=['POST'])
def upload_gl():
    """Upload GL (General Ledger) data"""
    try:
        file = request.files['file']
        df = pd.read_csv(file)
        
        # Validate required columns
        required_cols = ['date', 'account_code', 'description', 'debit', 'credit', 'reference']
        if not all(col in df.columns for col in required_cols):
            return jsonify({'error': 'Missing required columns: ' + ', '.join(required_cols)}), 400
        
        # Clean and validate data
        df['date'] = pd.to_datetime(df['date'])
        df['debit'] = pd.to_numeric(df['debit'], errors='coerce').fillna(0)
        df['credit'] = pd.to_numeric(df['credit'], errors='coerce').fillna(0)
        
        # Remove old GL entries
        conn = sqlite3.connect('reconciliation.db')
        c = conn.cursor()
        c.execute('DELETE FROM gl_entries')
        
        # Insert new GL entries
        for _, row in df.iterrows():
            c.execute('''INSERT INTO gl_entries 
                        (date, account_code, description, debit, credit, reference, uploaded_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (str(row['date']), row['account_code'], row['description'], 
                      row['debit'], row['credit'], row['reference'], datetime.now()))
        
        conn.commit()
        count = len(df)
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Uploaded {count} GL entries',
            'count': count
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload-bank', methods=['POST'])
def upload_bank():
    """Upload Bank Statement data"""
    try:
        file = request.files['file']
        df = pd.read_csv(file)
        
        # Validate required columns
        required_cols = ['date', 'amount', 'description', 'reference']
        if not all(col in df.columns for col in required_cols):
            return jsonify({'error': 'Missing required columns: ' + ', '.join(required_cols)}), 400
        
        # Clean and validate data
        df['date'] = pd.to_datetime(df['date'])
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        
        # Remove old bank entries
        conn = sqlite3.connect('reconciliation.db')
        c = conn.cursor()
        c.execute('DELETE FROM bank_entries')
        
        # Insert new bank entries
        for _, row in df.iterrows():
            bank_ref = row.get('bank_reference', '')
            c.execute('''INSERT INTO bank_entries 
                        (date, amount, description, reference, bank_reference, uploaded_at)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (str(row['date']), row['amount'], row['description'], 
                      row['reference'], bank_ref, datetime.now()))
        
        conn.commit()
        count = len(df)
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Uploaded {count} bank entries',
            'count': count
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reconcile', methods=['POST'])
def reconcile():
    """Run reconciliation process"""
    try:
        data = request.json
        tolerance = float(data.get('tolerance', 0.01))
        
        # Get GL and bank entries
        conn = sqlite3.connect('reconciliation.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute('SELECT * FROM gl_entries')
        gl_entries = [dict(row) for row in c.fetchall()]
        
        c.execute('SELECT * FROM bank_entries')
        bank_entries = [dict(row) for row in c.fetchall()]
        
        conn.close()
        
        # Run reconciliation
        matches, unmatched_gl, unmatched_bank = engine.reconcile(
            gl_entries, bank_entries, tolerance
        )
        
        # Save matches to database
        conn = sqlite3.connect('reconciliation.db')
        c = conn.cursor()
        
        # Clear old matches and exceptions
        c.execute('DELETE FROM reconciliation_matches')
        c.execute('DELETE FROM exceptions')
        
        # Save matches
        for match in matches:
            c.execute('''INSERT INTO reconciliation_matches 
                        (gl_entry_id, bank_entry_id, match_type, confidence_score, reconciled_at)
                        VALUES (?, ?, ?, ?, ?)''',
                     (match['gl_id'], match['bank_id'], match['type'], 
                      match['confidence'], datetime.now()))
        
        # Save unmatched GL entries as exceptions
        for gl in unmatched_gl:
            c.execute('''INSERT INTO exceptions 
                        (entry_type, entry_id, exception_type, description, amount, created_at, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     ('GL', gl['id'], 'Unmatched GL Entry', 
                      f"GL Entry: {gl['description']}", 
                      gl['debit'] - gl['credit'], datetime.now(), 'Open'))
        
        # Save unmatched bank entries as exceptions
        for bank in unmatched_bank:
            c.execute('''INSERT INTO exceptions 
                        (entry_type, entry_id, exception_type, description, amount, created_at, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     ('Bank', bank['id'], 'Unmatched Bank Entry', 
                      f"Bank Entry: {bank['description']}", 
                      bank['amount'], datetime.now(), 'Open'))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'matched': len(matches),
            'unmatched_gl': len(unmatched_gl),
            'unmatched_bank': len(unmatched_bank),
            'match_rate': round((len(matches) / (len(matches) + len(unmatched_gl) + len(unmatched_bank))) * 100, 2)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/summary', methods=['GET'])
def get_summary():
    """Get reconciliation summary"""
    try:
        conn = sqlite3.connect('reconciliation.db')
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) as count FROM gl_entries')
        gl_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) as count FROM bank_entries')
        bank_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) as count FROM reconciliation_matches')
        matched_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) as count FROM exceptions WHERE status = "Open"')
        exception_count = c.fetchone()[0]
        
        c.execute('SELECT SUM(amount) as total FROM exceptions WHERE status = "Open"')
        exception_amount = c.fetchone()[0] or 0
        
        conn.close()
        
        return jsonify({
            'gl_entries': gl_count,
            'bank_entries': bank_count,
            'matched_entries': matched_count,
            'open_exceptions': exception_count,
            'exception_amount': round(exception_amount, 2)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/matches', methods=['GET'])
def get_matches():
    """Get all matched entries"""
    try:
        conn = sqlite3.connect('reconciliation.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute('''SELECT 
                    m.id, m.match_type, m.confidence_score, m.reconciled_at,
                    gl.date as gl_date, gl.account_code, gl.description as gl_desc, 
                    gl.debit, gl.credit, gl.reference as gl_ref,
                    b.date as bank_date, b.amount, b.description as bank_desc, b.bank_reference
                    FROM reconciliation_matches m
                    JOIN gl_entries gl ON m.gl_entry_id = gl.id
                    JOIN bank_entries b ON m.bank_entry_id = b.id
                    ORDER BY m.reconciled_at DESC
                    LIMIT 100''')
        
        matches = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return jsonify(matches)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/exceptions', methods=['GET'])
def get_exceptions():
    """Get all exceptions"""
    try:
        conn = sqlite3.connect('reconciliation.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute('''SELECT * FROM exceptions 
                    WHERE status = "Open"
                    ORDER BY created_at DESC''')
        
        exceptions = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return jsonify(exceptions)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/exceptions/<int:exc_id>/resolve', methods=['POST'])
def resolve_exception(exc_id):
    """Resolve an exception"""
    try:
        data = request.json
        resolution = data.get('resolution', '')
        
        conn = sqlite3.connect('reconciliation.db')
        c = conn.cursor()
        
        c.execute('UPDATE exceptions SET status = ? WHERE id = ?', ('Resolved', exc_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Exception resolved'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-report', methods=['GET'])
def export_report():
    """Export reconciliation report as Excel"""
    try:
        conn = sqlite3.connect('reconciliation.db')
        
        # Get summary stats
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM gl_entries')
        total_gl = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM bank_entries')
        total_bank = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM reconciliation_matches')
        total_matched = c.fetchone()[0]
        
        # Create Excel with multiple sheets
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = {
                'Metric': ['GL Entries', 'Bank Entries', 'Matched', 'Unmatched GL', 'Unmatched Bank', 'Match Rate %'],
                'Count': [total_gl, total_bank, total_matched, 
                         total_gl - total_matched, total_bank - total_matched,
                         round((total_matched / max(total_gl, total_bank)) * 100, 2) if max(total_gl, total_bank) > 0 else 0]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
            
            # Matches sheet
            matches_df = pd.read_sql_query('''SELECT 
                                            m.id, m.match_type, m.confidence_score, m.reconciled_at,
                                            gl.date as gl_date, gl.account_code, gl.description, 
                                            gl.debit, gl.credit,
                                            b.date as bank_date, b.amount
                                            FROM reconciliation_matches m
                                            JOIN gl_entries gl ON m.gl_entry_id = gl.id
                                            JOIN bank_entries b ON m.bank_entry_id = b.id''', conn)
            matches_df.to_excel(writer, sheet_name='Matched Entries', index=False)
            
            # Exceptions sheet
            exceptions_df = pd.read_sql_query('''SELECT * FROM exceptions WHERE status = "Open"''', conn)
            exceptions_df.to_excel(writer, sheet_name='Exceptions', index=False)
            
            # Unmatched GL sheet
            unmatched_gl_df = pd.read_sql_query('''SELECT ge.* FROM gl_entries ge
                                                   WHERE ge.id NOT IN (SELECT gl_entry_id FROM reconciliation_matches)''', conn)
            unmatched_gl_df.to_excel(writer, sheet_name='Unmatched GL', index=False)
            
            # Unmatched Bank sheet
            unmatched_bank_df = pd.read_sql_query('''SELECT be.* FROM bank_entries be
                                                    WHERE be.id NOT IN (SELECT bank_entry_id FROM reconciliation_matches)''', conn)
            unmatched_bank_df.to_excel(writer, sheet_name='Unmatched Bank', index=False)
        
        conn.close()
        
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'Reconciliation_Report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
