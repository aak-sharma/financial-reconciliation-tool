import numpy as np
from difflib import SequenceMatcher
from datetime import datetime, timedelta
import json

class ReconciliationEngine:
    """Core reconciliation logic with multiple matching algorithms"""
    
    def __init__(self):
        self.matches = []
        self.unmatched_gl = []
        self.unmatched_bank = []
    
    def reconcile(self, gl_entries, bank_entries, tolerance=0.01):
        """
        Main reconciliation method combining multiple matching strategies
        
        Args:
            gl_entries: List of GL entries with debit/credit
            bank_entries: List of bank entries with amounts
            tolerance: Amount tolerance for matching (as decimal, e.g., 0.01 for 1%)
        
        Returns:
            (matches, unmatched_gl, unmatched_bank)
        """
        self.matches = []
        self.unmatched_gl = gl_entries.copy()
        self.unmatched_bank = bank_entries.copy()
        matched_gl_ids = set()
        matched_bank_ids = set()
        
        # Strategy 1: Exact amount matching (same day or within 3 days)
        for gl in gl_entries:
            gl_amount = gl['debit'] - gl['credit']  # Net amount
            for bank in bank_entries:
                if bank['id'] in matched_bank_ids:
                    continue
                if self._is_exact_match(gl_amount, bank['amount'], tolerance):
                    if self._is_date_within_range(gl['date'], bank['date'], 3):
                        self._create_match(gl, bank, 'Exact Amount Match', 0.95)
                        matched_gl_ids.add(gl['id'])
                        matched_bank_ids.add(bank['id'])
                        break
        
        # Strategy 2: Fuzzy text matching with amount tolerance
        for gl in gl_entries:
            if gl['id'] in matched_gl_ids:
                continue
            gl_amount = gl['debit'] - gl['credit']
            for bank in bank_entries:
                if bank['id'] in matched_bank_ids:
                    continue
                
                # Check if descriptions are similar
                similarity = self._text_similarity(
                    gl['description'].lower(),
                    bank['description'].lower()
                )
                
                if similarity > 0.7:  # 70% text match
                    amount_diff = abs(gl_amount - bank['amount'])
                    if amount_diff < tolerance * max(abs(gl_amount), abs(bank['amount'])):
                        if self._is_date_within_range(gl['date'], bank['date'], 5):
                            confidence = (similarity + 0.7) / 2  # Combine text and amount confidence
                            self._create_match(gl, bank, 'Fuzzy Text Match', min(confidence, 0.85))
                            matched_gl_ids.add(gl['id'])
                            matched_bank_ids.add(bank['id'])
                            break
        
        # Strategy 3: Reference number matching
        for gl in gl_entries:
            if gl['id'] in matched_gl_ids:
                continue
            for bank in bank_entries:
                if bank['id'] in matched_bank_ids:
                    continue
                
                # Extract reference numbers
                gl_refs = self._extract_references(gl['reference'])
                bank_refs = self._extract_references(bank['reference'] + ' ' + bank['bank_reference'])
                
                if gl_refs and bank_refs and any(ref in bank_refs for ref in gl_refs):
                    self._create_match(gl, bank, 'Reference Number Match', 0.90)
                    matched_gl_ids.add(gl['id'])
                    matched_bank_ids.add(bank['id'])
                    break
        
        # Strategy 4: Multi-entry matching (splits and consolidations)
        for gl in gl_entries:
            if gl['id'] in matched_gl_ids:
                continue
            gl_amount = gl['debit'] - gl['credit']
            
            # Look for multiple bank entries that sum to GL amount
            matching_banks = []
            for bank in bank_entries:
                if bank['id'] in matched_bank_ids:
                    continue
                if self._is_date_within_range(gl['date'], bank['date'], 5):
                    if abs(gl_amount - bank['amount']) < tolerance * abs(gl_amount):
                        matching_banks.append(bank)
            
            if matching_banks:
                total_bank = sum(b['amount'] for b in matching_banks)
                if abs(gl_amount - total_bank) < tolerance * abs(gl_amount):
                    # Create match for first bank entry
                    self._create_match(gl, matching_banks[0], 'Multi-Entry Match', 0.80)
                    matched_gl_ids.add(gl['id'])
                    for bank in matching_banks:
                        matched_bank_ids.add(bank['id'])
        
        # Remove matched entries from unmatched lists
        self.unmatched_gl = [e for e in self.unmatched_gl if e['id'] not in matched_gl_ids]
        self.unmatched_bank = [e for e in self.unmatched_bank if e['id'] not in matched_bank_ids]
        
        return self.matches, self.unmatched_gl, self.unmatched_bank
    
    def _is_exact_match(self, gl_amount, bank_amount, tolerance):
        """Check if amounts match within tolerance"""
        if gl_amount == 0 and bank_amount == 0:
            return True
        max_amount = max(abs(gl_amount), abs(bank_amount))
        if max_amount == 0:
            return True
        diff_percentage = abs(gl_amount - bank_amount) / max_amount
        return diff_percentage <= tolerance
    
    def _is_date_within_range(self, gl_date, bank_date, days=3):
        """Check if dates are within acceptable range"""
        try:
            gl_dt = self._parse_date(gl_date)
            bank_dt = self._parse_date(bank_date)
            diff = abs((bank_dt - gl_dt).days)
            return diff <= days
        except:
            return True
    
    def _parse_date(self, date_str):
        """Parse various date formats"""
        if isinstance(date_str, str):
            for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%m-%d-%Y', '%Y/%m/%d']:
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
            return datetime.now()
        return date_str
    
    def _text_similarity(self, text1, text2):
        """Calculate text similarity ratio"""
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _extract_references(self, ref_string):
        """Extract potential reference numbers from string"""
        if not ref_string:
            return []
        
        refs = []
        import re
        
        # Extract alphanumeric sequences
        tokens = re.findall(r'\b[A-Z0-9]{4,}\b', str(ref_string).upper())
        refs.extend(tokens)
        
        # Extract invoice numbers
        invoices = re.findall(r'INV\d+', str(ref_string).upper())
        refs.extend(invoices)
        
        # Extract check numbers
        checks = re.findall(r'CHK\d+', str(ref_string).upper())
        refs.extend(checks)
        
        return list(set(refs))
    
    def _create_match(self, gl_entry, bank_entry, match_type, confidence):
        """Create a match record"""
        gl_amount = gl_entry['debit'] - gl_entry['credit']
        
        match = {
            'gl_id': gl_entry['id'],
            'bank_id': bank_entry['id'],
            'type': match_type,
            'confidence': confidence,
            'gl_date': str(gl_entry['date']),
            'bank_date': str(bank_entry['date']),
            'gl_amount': gl_amount,
            'bank_amount': bank_entry['amount'],
            'variance': abs(gl_amount - bank_entry['amount']),
            'gl_description': gl_entry['description'],
            'bank_description': bank_entry['description']
        }
        
        self.matches.append(match)
        
        return match
    
    def get_reconciliation_stats(self):
        """Get reconciliation statistics"""
        total_entries = len(self.matches) + len(self.unmatched_gl) + len(self.unmatched_bank)
        
        if total_entries == 0:
            match_rate = 0
        else:
            match_rate = (len(self.matches) / total_entries) * 100
        
        return {
            'matched': len(self.matches),
            'unmatched_gl': len(self.unmatched_gl),
            'unmatched_bank': len(self.unmatched_bank),
            'match_rate': round(match_rate, 2),
            'avg_confidence': round(np.mean([m['confidence'] for m in self.matches]) if self.matches else 0, 3)
        }


class FinancialValidator:
    """Validate financial data quality"""
    
    @staticmethod
    def validate_gl_entry(entry):
        """Validate GL entry"""
        errors = []
        
        if not entry.get('date'):
            errors.append('Missing date')
        if not entry.get('account_code'):
            errors.append('Missing account code')
        if entry['debit'] < 0:
            errors.append('Debit cannot be negative')
        if entry['credit'] < 0:
            errors.append('Credit cannot be negative')
        if entry['debit'] > 0 and entry['credit'] > 0:
            errors.append('Cannot have both debit and credit')
        
        return errors
    
    @staticmethod
    def validate_bank_entry(entry):
        """Validate bank entry"""
        errors = []
        
        if not entry.get('date'):
            errors.append('Missing date')
        if not entry.get('amount'):
            errors.append('Missing amount')
        if not entry.get('description'):
            errors.append('Missing description')
        
        return errors
