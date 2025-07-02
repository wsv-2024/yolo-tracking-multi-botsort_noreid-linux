#!/usr/bin/env python3
"""
OCR Performance Monitor und Analyse-Tool

Dieses Script überwacht die OCR-Performance in Echtzeit und 
erstellt detaillierte Analysen der Erkennungsgenauigkeit.
"""

import os
import json
import time
import argparse
from datetime import datetime, timedelta
from collections import defaultdict, deque
import matplotlib.pyplot as plt
import pandas as pd


class OCRPerformanceMonitor:
    """Monitor für OCR-Performance-Tracking und -Analyse."""
    
    def __init__(self, log_file="logs/ocr_performance.jsonl"):
        self.log_file = log_file
        self.real_time_data = deque(maxlen=1000)  # Letzte 1000 OCR-Aufrufe
        self.last_read_position = 0
        
    def load_historical_data(self):
        """Lade historische OCR-Performance-Daten."""
        if not os.path.exists(self.log_file):
            return []
        
        data = []
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    data.append(entry)
                except json.JSONDecodeError:
                    continue
        return data
    
    def update_real_time_data(self):
        """Aktualisiere Real-Time-Daten aus Log-Datei."""
        if not os.path.exists(self.log_file):
            return
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                f.seek(self.last_read_position)
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        self.real_time_data.append(entry)
                    except json.JSONDecodeError:
                        continue
                self.last_read_position = f.tell()
        except Exception as e:
            print(f"Fehler beim Lesen der Log-Datei: {e}")
    
    def calculate_success_rate(self, data, time_window_hours=None):
        """Berechne Erfolgsrate für gegebene Daten."""
        if not data:
            return 0.0
        
        if time_window_hours:
            cutoff_time = time.time() - (time_window_hours * 3600)
            data = [d for d in data if d.get('timestamp', 0) > cutoff_time]
        
        if not data:
            return 0.0
        
        successful = len([d for d in data if d.get('text', '').strip()])
        return (successful / len(data)) * 100
    
    def analyze_method_performance(self, data):
        """Analysiere Performance nach OCR-Methoden."""
        method_stats = defaultdict(lambda: {
            'total': 0, 
            'success': 0, 
            'total_confidence': 0,
            'total_time': 0
        })
        
        for entry in data:
            method = entry.get('method', 'unknown')
            stats = method_stats[method]
            
            stats['total'] += 1
            stats['total_time'] += entry.get('execution_time', 0)
            stats['total_confidence'] += entry.get('confidence', 0)
            
            if entry.get('text', '').strip():
                stats['success'] += 1
        
        # Berechne Durchschnittswerte
        results = {}
        for method, stats in method_stats.items():
            if stats['total'] > 0:
                results[method] = {
                    'success_rate': (stats['success'] / stats['total']) * 100,
                    'avg_confidence': stats['total_confidence'] / stats['total'],
                    'avg_processing_time': stats['total_time'] / stats['total'],
                    'total_calls': stats['total']
                }
        
        return results
    
    def generate_performance_report(self, output_file=None):
        """Generiere detaillierten Performance-Report."""
        data = self.load_historical_data()
        
        if not data:
            report = "Keine OCR-Performance-Daten verfügbar."
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(report)
            return report
        
        # Zeiträume analysieren
        now = datetime.now()
        time_windows = {
            'Letzte Stunde': 1,
            'Letzte 24 Stunden': 24,
            'Letzte Woche': 168,
            'Gesamt': None
        }
        
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("OCR PERFORMANCE REPORT")
        report_lines.append(f"Generiert am: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 60)
        
        # Gesamtstatistiken
        total_calls = len(data)
        overall_success_rate = self.calculate_success_rate(data)
        avg_confidence = sum(d.get('confidence', 0) for d in data) / len(data)
        avg_processing_time = sum(d.get('execution_time', 0) for d in data) / len(data)
        
        report_lines.append(f"\nGESAMTSTATISTIKEN:")
        report_lines.append(f"  Gesamt OCR-Aufrufe: {total_calls:,}")
        report_lines.append(f"  Gesamte Erfolgsrate: {overall_success_rate:.1f}%")
        report_lines.append(f"  Durchschnittliche Confidence: {avg_confidence:.3f}")
        report_lines.append(f"  Durchschnittliche Verarbeitungszeit: {avg_processing_time:.3f}s")
        
        # Zeitfenster-Analyse
        report_lines.append(f"\nERFOLGSRATEN NACH ZEITFENSTERN:")
        for window_name, hours in time_windows.items():
            if hours is None:
                continue
            success_rate = self.calculate_success_rate(data, hours)
            cutoff_time = time.time() - (hours * 3600)
            window_data = [d for d in data if d.get('timestamp', 0) > cutoff_time]
            report_lines.append(f"  {window_name}: {success_rate:.1f}% ({len(window_data)} Aufrufe)")
        
        # Methoden-Analyse
        method_performance = self.analyze_method_performance(data)
        if method_performance:
            report_lines.append(f"\nPERFORMANCE NACH OCR-METHODEN:")
            for method, stats in sorted(method_performance.items(), 
                                      key=lambda x: x[1]['success_rate'], reverse=True):
                report_lines.append(f"  {method}:")
                report_lines.append(f"    Erfolgsrate: {stats['success_rate']:.1f}%")
                report_lines.append(f"    Ø Confidence: {stats['avg_confidence']:.3f}")
                report_lines.append(f"    Ø Verarbeitungszeit: {stats['avg_processing_time']:.3f}s")
                report_lines.append(f"    Anzahl Aufrufe: {stats['total_calls']}")
        
        # Textlängen-Analyse
        text_lengths = [len(d.get('text', '')) for d in data if d.get('text', '')]
        if text_lengths:
            report_lines.append(f"\nTEXTLÄNGEN-ANALYSE:")
            report_lines.append(f"  Durchschnittliche Textlänge: {sum(text_lengths)/len(text_lengths):.1f} Zeichen")
            report_lines.append(f"  Min/Max Textlänge: {min(text_lengths)}/{max(text_lengths)} Zeichen")
            
            # Erfolgsrate nach Textlänge
            short_texts = [d for d in data if len(d.get('text', '')) <= 5 and d.get('text', '')]
            long_texts = [d for d in data if len(d.get('text', '')) > 10 and d.get('text', '')]
            
            if short_texts:
                short_avg_conf = sum(d.get('confidence', 0) for d in short_texts) / len(short_texts)
                report_lines.append(f"  Kurze Texte (≤5 Zeichen): {len(short_texts)} Erkennungen, Ø Conf: {short_avg_conf:.3f}")
            
            if long_texts:
                long_avg_conf = sum(d.get('confidence', 0) for d in long_texts) / len(long_texts)
                report_lines.append(f"  Lange Texte (>10 Zeichen): {len(long_texts)} Erkennungen, Ø Conf: {long_avg_conf:.3f}")
        
        # Problematische Fälle
        low_confidence_cases = [d for d in data if d.get('confidence', 1) < 0.5]
        if low_confidence_cases:
            report_lines.append(f"\nPROBLEMATISCHE FÄLLE:")
            report_lines.append(f"  Niedrige Confidence (<0.5): {len(low_confidence_cases)} Fälle ({len(low_confidence_cases)/len(data)*100:.1f}%)")
        
        # Empfehlungen
        report_lines.append(f"\nEMPFEHLUNGEN:")
        
        if overall_success_rate < 70:
            report_lines.append("  ⚠️  Erfolgsrate unter 70% - Überprüfung der Bildqualität empfohlen")
        
        if avg_confidence < 0.6:
            report_lines.append("  ⚠️  Niedrige durchschnittliche Confidence - Bildvorverarbeitung optimieren")
        
        if avg_processing_time > 2.0:
            report_lines.append("  ⚠️  Hohe Verarbeitungszeit - GPU-Beschleunigung oder Parallelisierung prüfen")
        
        best_method = max(method_performance.items(), key=lambda x: x[1]['success_rate'])[0] if method_performance else None
        if best_method:
            report_lines.append(f"  ✅ Beste Methode: {best_method} - Verwendung priorisieren")
        
        report_lines.append("=" * 60)
        
        report = '\n'.join(report_lines)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"Report gespeichert in: {output_file}")
        
        return report
    
    def create_performance_charts(self, output_dir="charts"):
        """Erstelle Performance-Charts."""
        os.makedirs(output_dir, exist_ok=True)
        data = self.load_historical_data()
        
        if not data:
            print("Keine Daten für Charts verfügbar.")
            return
        
        # Chart 1: Erfolgsrate über Zeit
        plt.figure(figsize=(12, 6))
        
        # Gruppiere nach Stunden
        hourly_data = defaultdict(list)
        for entry in data:
            timestamp = entry.get('timestamp', 0)
            hour = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:00')
            hourly_data[hour].append(entry)
        
        hours = sorted(hourly_data.keys())
        success_rates = []
        
        for hour in hours:
            hour_data = hourly_data[hour]
            success_rate = self.calculate_success_rate(hour_data)
            success_rates.append(success_rate)
        
        plt.plot(range(len(hours)), success_rates, 'b-', linewidth=2)
        plt.title('OCR Erfolgsrate über Zeit')
        plt.xlabel('Zeit (Stunden)')
        plt.ylabel('Erfolgsrate (%)')
        plt.grid(True, alpha=0.3)
        plt.xticks(range(0, len(hours), max(1, len(hours)//10)), 
                  [hours[i] for i in range(0, len(hours), max(1, len(hours)//10))], 
                  rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'success_rate_over_time.png'), dpi=300)
        plt.close()
        
        # Chart 2: Methoden-Vergleich
        method_performance = self.analyze_method_performance(data)
        if method_performance:
            plt.figure(figsize=(10, 6))
            
            methods = list(method_performance.keys())
            success_rates = [method_performance[m]['success_rate'] for m in methods]
            
            bars = plt.bar(methods, success_rates)
            plt.title('OCR Erfolgsrate nach Methoden')
            plt.xlabel('OCR-Methode')
            plt.ylabel('Erfolgsrate (%)')
            plt.xticks(rotation=45)
            
            # Färbe Balken basierend auf Performance
            for i, bar in enumerate(bars):
                if success_rates[i] >= 80:
                    bar.set_color('green')
                elif success_rates[i] >= 60:
                    bar.set_color('orange')
                else:
                    bar.set_color('red')
            
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, 'method_comparison.png'), dpi=300)
            plt.close()
        
        # Chart 3: Confidence-Verteilung
        confidences = [d.get('confidence', 0) for d in data if d.get('text', '')]
        if confidences:
            plt.figure(figsize=(10, 6))
            plt.hist(confidences, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
            plt.title('Verteilung der OCR-Confidence-Werte')
            plt.xlabel('Confidence')
            plt.ylabel('Anzahl')
            plt.axvline(x=sum(confidences)/len(confidences), color='red', 
                       linestyle='--', label=f'Durchschnitt: {sum(confidences)/len(confidences):.3f}')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, 'confidence_distribution.png'), dpi=300)
            plt.close()
        
        print(f"Charts gespeichert in: {output_dir}/")
    
    def real_time_monitor(self, refresh_interval=10):
        """Real-Time OCR-Performance Monitoring."""
        print("Starte Real-Time OCR Monitor...")
        print("Drücke Ctrl+C zum Beenden")
        
        try:
            while True:
                self.update_real_time_data()
                
                if self.real_time_data:
                    recent_data = list(self.real_time_data)[-100:]  # Letzte 100 Aufrufe
                    success_rate = self.calculate_success_rate(recent_data)
                    avg_confidence = sum(d.get('confidence', 0) for d in recent_data) / len(recent_data)
                    
                    # Aktueller Status
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    print(f"\r[{timestamp}] OCR Monitor - "
                          f"Erfolgsrate: {success_rate:.1f}% | "
                          f"Ø Confidence: {avg_confidence:.3f} | "
                          f"Aufrufe: {len(recent_data)}", end='', flush=True)
                else:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    print(f"\r[{timestamp}] OCR Monitor - Warten auf Daten...", end='', flush=True)
                
                time.sleep(refresh_interval)
        
        except KeyboardInterrupt:
            print("\nReal-Time Monitor gestoppt.")


def main():
    """Hauptfunktion für Command-Line Interface."""
    parser = argparse.ArgumentParser(description='OCR Performance Monitor')
    parser.add_argument('--report', action='store_true', 
                       help='Generiere Performance-Report')
    parser.add_argument('--charts', action='store_true', 
                       help='Erstelle Performance-Charts')
    parser.add_argument('--monitor', action='store_true', 
                       help='Starte Real-Time Monitor')
    parser.add_argument('--output', type=str, default='ocr_report.txt',
                       help='Output-Datei für Report')
    parser.add_argument('--log-file', type=str, default='logs/ocr_performance.jsonl',
                       help='Pfad zur OCR-Log-Datei')
    
    args = parser.parse_args()
    
    monitor = OCRPerformanceMonitor(args.log_file)
    
    if args.report:
        print("Generiere OCR Performance Report...")
        report = monitor.generate_performance_report(args.output)
        print(report)
    
    if args.charts:
        print("Erstelle Performance Charts...")
        monitor.create_performance_charts()
    
    if args.monitor:
        monitor.real_time_monitor()
    
    if not any([args.report, args.charts, args.monitor]):
        # Standard: Kurzer Status
        print("OCR Performance Monitor")
        print("-" * 30)
        data = monitor.load_historical_data()
        if data:
            success_rate = monitor.calculate_success_rate(data, 24)  # Letzte 24h
            print(f"Erfolgsrate (24h): {success_rate:.1f}%")
            print(f"Gesamt OCR-Aufrufe: {len(data):,}")
            
            recent_data = [d for d in data if d.get('timestamp', 0) > time.time() - 3600]  # Letzte Stunde
            if recent_data:
                print(f"Letzte Stunde: {len(recent_data)} Aufrufe")
        else:
            print("Keine OCR-Daten verfügbar.")
        
        print("\nVerwende --help für weitere Optionen.")


if __name__ == "__main__":
    main()
