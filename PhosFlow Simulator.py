import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from scipy.interpolate import PchipInterpolator
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QMessageBox, 
                             QSlider, QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QComboBox, QAbstractItemView)
from PyQt5.QtCore import Qt, QTimer
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class SimulateurSCADA(QMainWindow):
    def __init__(self):
        super().__init__()
        
        try:
            fichier_excel = r"C:\Users\dell\Desktop\Parametres_OCP.xlsx"
            df_topo = pd.read_excel(fichier_excel, sheet_name='Topographie')
            self.X = np.arange(0, 187.5, 0.5)
            self.D = 0.850
            
            interpolateur = PchipInterpolator(df_topo['Distance_km'].values, df_topo['Altitude_m'].values)
            self.Z = interpolateur(self.X)
            
            self.HGL_Max_MAOP = self.Z + 1100
            self.HGL_Min_Cav = self.Z + 10
            
            df_caps = pd.read_excel(fichier_excel, sheet_name='Capteurs')
            self.noms_stations = list(df_caps['Nom_Station'].values)
            self.dist_stations = list(df_caps['Distance_km'].values)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Fichier Excel introuvable :\n{str(e)}")
            sys.exit()

        self.t_sim = datetime.strptime('00:00:00', '%H:%M:%S')
        self.current_inj = 0 
        self.segments = [{'type': 0, 'start': 0.0, 'end': 187.25, 'density': np.nan}]
        self.mode_config = False 
        
        self.pressions_forcees = {}
        self.densites_forcees = {}
            
        self.setWindowTitle("Supervision SCADA OCP - Écoulement Continu et Dynamique")
        self.setGeometry(50, 50, 1400, 800) 
        
        widget_principal = QWidget()
        self.setCentralWidget(widget_principal)
        layout_principal = QVBoxLayout(widget_principal)

        layout_header = QHBoxLayout()
        self.lbl_horloge = QLabel("Horloge : 00:00:00")
        self.lbl_horloge.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.lbl_statut = QLabel("STATUT : PIPELINE VIDE")
        self.lbl_statut.setStyleSheet("font-size: 18px; font-weight: bold; color: gray;")
        layout_header.addWidget(self.lbl_horloge)
        layout_header.addWidget(self.lbl_statut)
        layout_principal.addLayout(layout_header)

        layout_central = QHBoxLayout()
        
        self.figure, self.ax = plt.subplots(figsize=(9, 4))
        self.canvas = FigureCanvas(self.figure)
        self.ax.set_xlim(0, 190)
        self.ax.set_ylim(0, 1800)
        self.ax.set_ylabel("HGL Local (mètres)")
        self.ax.grid(True)
        
        self.ax.fill_between(list(self.X) + [187.25, 0], list(self.Z) + [0, 0], color='lightgray')
        self.ax.plot(self.X, self.HGL_Max_MAOP, 'r--', linewidth=1.5)
        self.ax.plot(self.X, self.HGL_Min_Cav, 'r:', linewidth=1.5)
        self.ax.plot(self.X, self.Z, 'k-', linewidth=4)
        
        self.lignes_stations = []
        self.texts_stations = []
        for i in range(len(self.noms_stations)):
            dist = self.dist_stations[i]
            nom = self.noms_stations[i]
            couleur_ligne = 'm' if "PMS" in str(nom) else 'dimgray'
            vline = self.ax.axvline(x=dist, color=couleur_ligne, linestyle=':', linewidth=1.5)
            self.lignes_stations.append(vline)
            txt = self.ax.text(dist + 0.5, 1750, f"{nom} : -- Bar", color=couleur_ligne, fontsize=9, fontweight='bold', rotation=90, verticalalignment='top')
            self.texts_stations.append(txt)
        
        self.line_hgl, = self.ax.plot(self.X, np.full_like(self.X, np.nan), 'b-', linewidth=2.5)
        self.scatter_fluids = self.ax.scatter(self.X, self.Z, c='lightgray', s=35, zorder=3)
        self.line_interfaces, = self.ax.plot([], [], '^', color='lime', markersize=8, markeredgecolor='black', zorder=5)
        
        layout_central.addWidget(self.canvas, stretch=7) 

        layout_tableaux = QVBoxLayout()
        
        self.btn_mode_config = QPushButton("🛠️ ACTIVER MODE CONFIGURATION")
        self.btn_mode_config.setStyleSheet("background-color: #ffd966; font-weight: bold; padding: 8px; font-size: 14px;")
        self.btn_mode_config.clicked.connect(self.activer_mode_config)
        
        self.lbl_batch = QLabel("1. Batches (Temps Réel)")
        self.lbl_batch.setStyleSheet("font-weight: bold; color: purple; font-size: 14px;")
        
        self.table_batches = QTableWidget(0, 3)
        self.table_batches.setHorizontalHeaderLabels(["Product", "Start km", "Wt%Sol"])
        self.table_batches.verticalHeader().setVisible(True) 
        self.table_batches.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        h_batch_btns = QHBoxLayout()
        self.btn_add_row = QPushButton("➕ Ajouter Lot")
        self.btn_del_row = QPushButton("➖ Supprimer Lot")
        self.btn_appliquer_profil = QPushButton("✅ APPLIQUER LE SCÉNARIO")
        self.btn_appliquer_profil.setStyleSheet("background-color: #93c47d; font-weight: bold;")
        
        self.btn_add_row.setVisible(False)
        self.btn_del_row.setVisible(False)
        self.btn_appliquer_profil.setVisible(False)
        
        self.btn_add_row.clicked.connect(self.ajouter_ligne_batch)
        self.btn_del_row.clicked.connect(self.supprimer_ligne_batch)
        self.btn_appliquer_profil.clicked.connect(self.appliquer_profil)
        
        h_batch_btns.addWidget(self.btn_add_row)
        h_batch_btns.addWidget(self.btn_del_row)
        h_batch_btns.addWidget(self.btn_appliquer_profil)
        
        lbl_tele = QLabel("2. Télémétrie Capteurs (Éditable)")
        lbl_tele.setStyleSheet("font-weight: bold; color: blue;")
        self.table_capteurs = QTableWidget(len(self.noms_stations), 4)
        self.table_capteurs.setHorizontalHeaderLabels(["Station", "PK (km)", "Pression (Bar)", "Densité"])
        self.table_capteurs.verticalHeader().setVisible(False) 
        self.table_capteurs.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) 
        
        for i in range(len(self.noms_stations)):
            item_nom = QTableWidgetItem(f"{self.noms_stations[i]}")
            item_pk = QTableWidgetItem(f"{self.dist_stations[i]:.2f}")
            item_pk.setTextAlignment(Qt.AlignCenter)
            
            item_p = QTableWidgetItem("0.00")
            item_p.setTextAlignment(Qt.AlignCenter)
            
            item_d = QTableWidgetItem("Vide")
            item_d.setTextAlignment(Qt.AlignCenter)
            
            self.table_capteurs.setItem(i, 0, item_nom)
            self.table_capteurs.setItem(i, 1, item_pk)
            self.table_capteurs.setItem(i, 2, item_p)
            self.table_capteurs.setItem(i, 3, item_d)
            
        self.table_capteurs.itemChanged.connect(self.on_capteur_changed)
            
        layout_tableaux.addWidget(self.btn_mode_config)
        layout_tableaux.addWidget(self.lbl_batch)
        layout_tableaux.addWidget(self.table_batches, stretch=1)
        layout_tableaux.addLayout(h_batch_btns)
        layout_tableaux.addWidget(lbl_tele)
        layout_tableaux.addWidget(self.table_capteurs, stretch=1)
        
        layout_central.addLayout(layout_tableaux, stretch=3) 
        layout_principal.addLayout(layout_central)

        layout_controles = QHBoxLayout()
        layout_sliders_tete = QVBoxLayout()
        
        h_q = QHBoxLayout(); lbl_q = QLabel("Débit Pompe (m3/h) :"); lbl_q.setStyleSheet("font-weight: bold;")
        self.spn_q = QSpinBox(); self.spn_q.setRange(3500, 5000); self.spn_q.setValue(4000)
        h_q.addWidget(lbl_q); h_q.addWidget(self.spn_q)
        self.sld_q = QSlider(Qt.Horizontal); self.sld_q.setRange(3500, 5000); self.sld_q.setValue(4000)
        self.sld_q.valueChanged.connect(self.spn_q.setValue); self.spn_q.valueChanged.connect(self.sld_q.setValue)
        
        h_p = QHBoxLayout(); lbl_p = QLabel("Pression Tête 0 km (Bar) :"); lbl_p.setStyleSheet("font-weight: bold; color: blue;")
        self.spn_p = QSpinBox(); self.spn_p.setRange(10, 120); self.spn_p.setValue(55)
        h_p.addWidget(lbl_p); h_p.addWidget(self.spn_p)
        self.sld_p = QSlider(Qt.Horizontal); self.sld_p.setRange(10, 120); self.sld_p.setValue(55)
        self.sld_p.valueChanged.connect(self.spn_p.setValue); self.spn_p.valueChanged.connect(self.sld_p.setValue)
        
        h_d = QHBoxLayout(); lbl_d = QLabel("Densité Pulpe (kg/m³) :"); lbl_d.setStyleSheet("font-weight: bold; color: darkorange;")
        self.spn_d = QSpinBox(); self.spn_d.setRange(1000, 1800); self.spn_d.setValue(1600)
        h_d.addWidget(lbl_d); h_d.addWidget(self.spn_d)
        self.sld_d = QSlider(Qt.Horizontal); self.sld_d.setRange(1000, 1800); self.sld_d.setValue(1600)
        self.sld_d.valueChanged.connect(self.spn_d.setValue); self.spn_d.valueChanged.connect(self.sld_d.setValue)

        self.spn_q.valueChanged.connect(self.actualiser_graphique_instantane)
        self.spn_p.valueChanged.connect(self.actualiser_graphique_instantane)
        self.spn_d.valueChanged.connect(self.actualiser_graphique_instantane)

        layout_sliders_tete.addLayout(h_q); layout_sliders_tete.addWidget(self.sld_q)
        layout_sliders_tete.addLayout(h_p); layout_sliders_tete.addWidget(self.sld_p)
        layout_sliders_tete.addLayout(h_d); layout_sliders_tete.addWidget(self.sld_d)
        
        layout_sliders_pms = QVBoxLayout()
        h_pms1 = QHBoxLayout(); lbl_pms1 = QLabel("Appoint PMS-1 (Bar) :"); lbl_pms1.setStyleSheet("font-weight: bold; color: magenta;")
        self.spn_pms1 = QSpinBox(); self.spn_pms1.setRange(-30, 60); self.spn_pms1.setValue(0)
        h_pms1.addWidget(lbl_pms1); h_pms1.addWidget(self.spn_pms1)
        self.sld_pms1 = QSlider(Qt.Horizontal); self.sld_pms1.setRange(-30, 60); self.sld_pms1.setValue(0)
        self.sld_pms1.valueChanged.connect(self.spn_pms1.setValue); self.spn_pms1.valueChanged.connect(self.sld_pms1.setValue)
        
        h_pms2 = QHBoxLayout(); lbl_pms2 = QLabel("Appoint PMS-2 (Bar) :"); lbl_pms2.setStyleSheet("font-weight: bold; color: magenta;")
        self.spn_pms2 = QSpinBox(); self.spn_pms2.setRange(-30, 60); self.spn_pms2.setValue(0)
        h_pms2.addWidget(lbl_pms2); h_pms2.addWidget(self.spn_pms2)
        self.sld_pms2 = QSlider(Qt.Horizontal); self.sld_pms2.setRange(-30, 60); self.sld_pms2.setValue(0)
        self.sld_pms2.valueChanged.connect(self.spn_pms2.setValue); self.spn_pms2.valueChanged.connect(self.sld_pms2.setValue)

        self.spn_pms1.valueChanged.connect(self.actualiser_graphique_instantane)
        self.spn_pms2.valueChanged.connect(self.actualiser_graphique_instantane)

        layout_sliders_pms.addLayout(h_pms1); layout_sliders_pms.addWidget(self.sld_pms1)
        layout_sliders_pms.addLayout(h_pms2); layout_sliders_pms.addWidget(self.sld_pms2)
        
        layout_boutons = QVBoxLayout()
        self.btn_eau = QPushButton("INJECTER EAU"); self.btn_eau.setStyleSheet("background-color: lightblue; font-weight: bold; padding: 10px;")
        self.btn_pulpe = QPushButton("INJECTER PULPE"); self.btn_pulpe.setStyleSheet("background-color: orange; font-weight: bold; padding: 10px;")
        self.btn_stop = QPushButton("STOP INJECTION"); self.btn_stop.setStyleSheet("background-color: lightgray; font-weight: bold; padding: 10px;")
        
        layout_sys = QHBoxLayout()
        self.btn_reset = QPushButton("🔄 RESET"); self.btn_reset.setStyleSheet("background-color: #ffcccc; font-weight: bold; border: 2px solid #cc0000; color: #cc0000;")
        self.btn_quitter = QPushButton("❌ QUITTER"); self.btn_quitter.setStyleSheet("background-color: #cc0000; font-weight: bold; color: white;")
        layout_sys.addWidget(self.btn_reset); layout_sys.addWidget(self.btn_quitter)
        
        layout_boutons.addWidget(self.btn_eau); layout_boutons.addWidget(self.btn_pulpe); layout_boutons.addWidget(self.btn_stop); layout_boutons.addLayout(layout_sys)
        layout_controles.addLayout(layout_sliders_tete, stretch=2); layout_controles.addLayout(layout_sliders_pms, stretch=2); layout_controles.addLayout(layout_boutons, stretch=1)
        layout_principal.addLayout(layout_controles)

        self.btn_eau.clicked.connect(lambda: self.set_injection(1))
        self.btn_pulpe.clicked.connect(lambda: self.set_injection(2))
        self.btn_stop.clicked.connect(lambda: self.set_injection(0))
        self.btn_reset.clicked.connect(self.reset_simulation)
        self.btn_quitter.clicked.connect(self.close) 

        self.update_simulation(premier_lancement=True)
        self.timer = QTimer()
        self.timer.timeout.connect(lambda: self.update_simulation(premier_lancement=False))
        self.timer.start(1000) 

    def actualiser_graphique_instantane(self):
        self.update_simulation(premier_lancement=True)

    def on_capteur_changed(self, item):
        col = item.column()
        row = item.row()
        
        if col == 0:
            self.noms_stations[row] = item.text()
            dist = self.dist_stations[row]
            couleur_ligne = 'm' if "PMS" in str(self.noms_stations[row]) else 'dimgray'
            self.lignes_stations[row].set_color(couleur_ligne)
        elif col == 1:
            try:
                nouveau_pk = float(item.text().replace(',', '.'))
                nouveau_pk = max(0.0, min(187.25, nouveau_pk))
                self.dist_stations[row] = nouveau_pk
                dist = nouveau_pk
                nom = self.noms_stations[row]
                couleur_ligne = 'm' if "PMS" in str(nom) else 'dimgray'
                
                self.lignes_stations[row].set_xdata([dist, dist])
                self.texts_stations[row].set_position((dist + 0.5, 1750))
                self.canvas.draw_idle()
            except ValueError:
                pass
        elif col == 2:
            val = item.text().strip()
            if val == "" or val.lower() == "auto":
                if row in self.pressions_forcees:
                    del self.pressions_forcees[row]
            else:
                self.pressions_forcees[row] = val
        elif col == 3:
            val = item.text().strip()
            if val == "" or val.lower() == "auto":
                if row in self.densites_forcees:
                    del self.densites_forcees[row]
            else:
                self.densites_forcees[row] = val

    def activer_mode_config(self):
        self.mode_config = True
        self.lbl_batch.setText("🛠️ Batches (MODE ÉDITION)")
        self.lbl_batch.setStyleSheet("font-weight: bold; color: red; font-size: 14px;")
        self.btn_mode_config.setVisible(False)
        self.btn_add_row.setVisible(True)
        self.btn_del_row.setVisible(True)
        self.btn_appliquer_profil.setVisible(True)
        
        self.table_batches.setEditTriggers(QTableWidget.AllEditTriggers)
        for r in range(self.table_batches.rowCount()):
            combo = self.table_batches.cellWidget(r, 0)
            if combo: 
                combo.setEnabled(True)
                combo.currentIndexChanged.connect(self.on_combo_changed)

    def on_combo_changed(self):
        combo = self.sender()
        if combo:
            for r in range(self.table_batches.rowCount()):
                if self.table_batches.cellWidget(r, 0) == combo:
                    prod = combo.currentText()
                    if prod == "Water": self.table_batches.setItem(r, 2, QTableWidgetItem("0"))
                    elif prod == "Slurry":
                        actuel = self.table_batches.item(r, 2)
                        if not actuel or actuel.text() == "0" or actuel.text() == "":
                            self.table_batches.setItem(r, 2, QTableWidgetItem("50"))
                    elif prod == "Vide": self.table_batches.setItem(r, 2, QTableWidgetItem(""))
                    break

    def ajouter_ligne_batch(self):
        ligne = self.table_batches.rowCount()
        self.table_batches.insertRow(ligne)
        combo = QComboBox()
        combo.addItems(["Vide", "Water", "Slurry"])
        combo.currentIndexChanged.connect(self.on_combo_changed)
        self.table_batches.setCellWidget(ligne, 0, combo)
        self.table_batches.setItem(ligne, 1, QTableWidgetItem("0.0"))
        self.table_batches.setItem(ligne, 2, QTableWidgetItem(""))

    def supprimer_ligne_batch(self):
        ligne = self.table_batches.currentRow()
        if ligne >= 0: self.table_batches.removeRow(ligne)

    def appliquer_profil(self):
        nouveaux_segments = []
        lignes = self.table_batches.rowCount()
        try:
            for r in range(lignes):
                combo = self.table_batches.cellWidget(r, 0)
                item_km = self.table_batches.item(r, 1)
                item_sol = self.table_batches.item(r, 2)
                
                if combo and item_km and item_sol:
                    prod = combo.currentText()
                    try: km_start = float(item_km.text().replace(',', '.'))
                    except ValueError: continue
                    
                    sol_text = item_sol.text().replace(',', '.')
                    if prod == "Vide": typ = 0; dens = np.nan
                    elif prod == "Water": typ = 1; dens = 1000.0
                    else:
                        typ = 2; 
                        try: sol = float(sol_text) if sol_text != "" else 50.0
                        except ValueError: sol = 50.0
                        dens = 1000.0 + sol * 10
                        
                    nouveaux_segments.append({'type': typ, 'start': km_start, 'density': dens})
                    
            if not nouveaux_segments:
                nouveaux_segments = [{'type': 0, 'start': 0.0, 'end': 187.25, 'density': np.nan}]
            else:
                nouveaux_segments.sort(key=lambda x: x['start'])
                if nouveaux_segments[0]['start'] > 0.0:
                    fill_type = self.current_inj if self.current_inj > 0 else nouveaux_segments[0]['type']
                    fill_dens = float(self.spn_d.value()) if fill_type == 2 else 1000.0 if fill_type == 1 else np.nan
                    nouveaux_segments.insert(0, {'type': fill_type, 'start': 0.0, 'density': fill_dens})
                else:
                    nouveaux_segments[0]['start'] = 0.0 

                for i in range(len(nouveaux_segments)-1):
                    nouveaux_segments[i]['end'] = nouveaux_segments[i+1]['start']
                nouveaux_segments[-1]['end'] = 187.25
                
            cleaned_segments = []
            for seg in nouveaux_segments:
                if seg['start'] >= 187.25: continue 
                if len(cleaned_segments) > 0 and cleaned_segments[-1]['type'] == seg['type'] and cleaned_segments[-1]['density'] == seg['density']:
                    cleaned_segments[-1]['end'] = seg['end']
                else:
                    cleaned_segments.append(seg)

            self.segments = cleaned_segments
            
            self.mode_config = False
            self.lbl_batch.setText("1. Batches (Temps Réel)")
            self.lbl_batch.setStyleSheet("font-weight: bold; color: purple; font-size: 14px;")
            self.btn_mode_config.setVisible(True)
            self.btn_add_row.setVisible(False)
            self.btn_del_row.setVisible(False)
            self.btn_appliquer_profil.setVisible(False)
            
            # --- DÉMARRAGE AUTOMATIQUE ---
            # Le simulateur lie le fluide situé au km 0 et active la pompe correspondante.
            if len(self.segments) > 0 and self.segments[0]['type'] > 0:
                self.current_inj = self.segments[0]['type']
            else:
                self.current_inj = 0
                
            self.update_simulation(premier_lancement=True)
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Erreur de saisie : {str(e)}")

    def synchroniser_tableau_avec_physique(self):
        if self.mode_config: return 
            
        self.table_batches.blockSignals(True) 
        self.table_batches.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_batches.setRowCount(len(self.segments))
        
        for i, seg in enumerate(self.segments):
            combo = QComboBox()
            combo.addItems(["Vide", "Water", "Slurry"])
            if seg['type'] == 0: combo.setCurrentText("Vide")
            elif seg['type'] == 1: combo.setCurrentText("Water")
            elif seg['type'] == 2: combo.setCurrentText("Slurry")
            combo.setEnabled(False) 
            self.table_batches.setCellWidget(i, 0, combo)
            
            self.table_batches.setItem(i, 1, QTableWidgetItem(f"{seg['start']:.2f}"))
            
            if seg['type'] == 0: self.table_batches.setItem(i, 2, QTableWidgetItem(""))
            elif seg['type'] == 1: self.table_batches.setItem(i, 2, QTableWidgetItem("0"))
            else:
                wt = (seg['density'] - 1000) / 10 
                self.table_batches.setItem(i, 2, QTableWidgetItem(f"{wt:.0f}"))
                
        self.table_batches.blockSignals(False)

    def set_injection(self, type_inj):
        self.current_inj = type_inj
        self.update_simulation(premier_lancement=True)

    def reset_simulation(self):
        self.current_inj = 0
        self.segments = [{'type': 0, 'start': 0.0, 'end': 187.25, 'density': np.nan}]
        self.t_sim = datetime.strptime('00:00:00', '%H:%M:%S') - timedelta(seconds=20)
        self.spn_q.setValue(4000); self.spn_p.setValue(55); self.spn_d.setValue(1600)
        self.mode_config = False
        self.pressions_forcees = {}
        self.densites_forcees = {}
        self.btn_mode_config.setVisible(True)
        self.btn_add_row.setVisible(False); self.btn_del_row.setVisible(False); self.btn_appliquer_profil.setVisible(False)
        self.update_simulation(premier_lancement=False)

    def update_simulation(self, premier_lancement=False):
        Q_act = self.spn_q.value()
        P_tete = self.spn_p.value() * 1e5
        P_appoint1 = self.spn_pms1.value() * 1e5
        P_appoint2 = self.spn_pms2.value() * 1e5
        densite_tete = float(self.spn_d.value())
        
        if not premier_lancement:
            self.t_sim += timedelta(seconds=20)
            self.lbl_horloge.setText(f"Horloge : {self.t_sim.strftime('%H:%M:%S')}")
            
            if self.current_inj == 0: dx = 0.0
            else:
                V = (Q_act / 3600.0) / (np.pi * (self.D**2) / 4.0)
                dx = (V * 20.0) / 1000.0 
            
            if dx > 0:
                for seg in self.segments:
                    seg['start'] += dx; seg['end'] += dx
                    
                if self.current_inj == 1: current_dens = 1000.0
                elif self.current_inj == 2: current_dens = densite_tete
                
                if len(self.segments) > 0 and self.segments[0]['type'] == self.current_inj and abs(self.segments[0]['density'] - current_dens) < 1.0:
                    self.segments[0]['start'] = 0.0
                else:
                    self.segments.insert(0, {'type': self.current_inj, 'start': 0.0, 'end': dx, 'density': current_dens})
                    
                keep = []
                for seg in self.segments:
                    if seg['start'] < 187.25:
                        if seg['end'] > 187.25: seg['end'] = 187.25
                        keep.append(seg)
                self.segments = keep

        types = np.zeros_like(self.X)
        rho_f = np.full_like(self.X, np.nan)
        
        for seg in self.segments:
            idx = (self.X >= seg['start']) & (self.X <= seg['end'])
            types[idx] = seg['type']
            rho_f[idx] = seg.get('density', np.nan)

        self.synchroniser_tableau_avec_physique()

        J_eau = 0.0015 * (Q_act / 4000.0)**2
        J_pulpe = 0.00343 * (Q_act / 4000.0)**2
        
        P = np.zeros_like(self.X)
        HGL = np.zeros_like(self.X)
        colors = np.full((len(self.X), 4), [0.8, 0.8, 0.8, 1.0]) 
        
        if types[0] == 0 or np.isnan(rho_f[0]):
            P[0] = 0
            HGL[0] = self.Z[0]
            colors[0] = [0.8, 0.8, 0.8, 1.0]
            rho_0 = 1000.0 
        else:
            P[0] = P_tete
            rho_0 = rho_f[0]
            HGL[0] = self.Z[0] + P[0] / (rho_0 * 9.81)
            
            if types[0] == 1: colors[0] = [0.0, 1.0, 1.0, 1.0]
            else: colors[0] = [0.75, 0.45, 0.15, 1.0] 
        
        for i in range(1, len(self.X)):
            rho = rho_f[i]
            t = types[i]
            
            if np.isnan(rho) or t == 0:
                P[i] = 0
                HGL[i] = self.Z[i]
                colors[i] = [0.8, 0.8, 0.8, 1.0]
            else:
                if t == 1: 
                    J = J_eau
                    colors[i] = [0.0, 1.0, 1.0, 1.0] 
                elif t == 2:
                    J = J_pulpe
                    colors[i] = [0.75, 0.45, 0.15, 1.0] 
                
                dP_grav = rho * 9.81 * (self.Z[i] - self.Z[i-1])
                dP_frot = rho * 9.81 * J * 500.0 
                
                P[i] = P[i-1] - dP_grav - dP_frot
                
                if self.X[i-1] < 46.0 and self.X[i] >= 46.0: P[i] += P_appoint1
                if self.X[i-1] < 100.5 and self.X[i] >= 100.5: P[i] += P_appoint2
                
                if P[i] < 0: P[i] = 0
                
                HGL[i] = self.Z[i] + P[i] / (rho * 9.81)
        
        ix = []; iy = []
        for seg in self.segments:
            if seg['type'] > 0 and seg['start'] < 187.0 and seg['start'] > 0: 
                idx = (np.abs(self.X - seg['start'])).argmin()
                ix.append(self.X[idx])
                iy.append(HGL[idx])
        self.line_interfaces.set_data(ix, iy)

        slack_detecte = np.any((P[1:] == 0) & (types[1:] > 0))
        
        self.table_capteurs.blockSignals(True)
        
        is_editing = (self.table_capteurs.state() == QAbstractItemView.EditingState)
        current_row = self.table_capteurs.currentRow()
        current_col = self.table_capteurs.currentColumn()
        
        for i in range(len(self.dist_stations)):
            idx = (np.abs(self.X - self.dist_stations[i])).argmin()
            pression_bar = P[idx] / 1e5
            densite_val = rho_f[idx]
            nom = self.noms_stations[i]
            
            if np.isnan(densite_val) or types[idx] == 0 or pression_bar <= 0:
                p_text_calc = "0.00"; d_text_calc = "Vide"; couleur_fond = Qt.white
            else:
                p_text_calc = f"{pression_bar:.2f}"; d_text_calc = f"{densite_val:.0f}"
                if densite_val >= 1500: couleur_fond = Qt.yellow
                elif densite_val > 1000: couleur_fond = Qt.green
                else: couleur_fond = Qt.cyan
                
            p_text = self.pressions_forcees.get(i, p_text_calc)
            d_text = self.densites_forcees.get(i, d_text_calc)
                
            self.texts_stations[i].set_text(f"{nom} : {p_text} Bar")
            
            item_p = self.table_capteurs.item(i, 2)
            if not (is_editing and current_row == i and current_col == 2):
                if item_p.text() != p_text:
                    item_p.setText(p_text)
            
            item_d = self.table_capteurs.item(i, 3)
            if not (is_editing and current_row == i and current_col == 3):
                if item_d.text() != d_text:
                    item_d.setText(d_text)
            item_d.setBackground(couleur_fond)
            
        self.table_capteurs.blockSignals(False)

        if np.all(types == 0):
            self.lbl_statut.setText("STATUT : PIPELINE VIDE")
        elif np.any(HGL > self.HGL_Max_MAOP):
            self.lbl_statut.setText("!!! DANGER : SURPRESSION MAOP !!!")
            self.lbl_statut.setStyleSheet("font-size: 18px; font-weight: bold; color: red;")
        elif slack_detecte:
            self.lbl_statut.setText("STATUT : SLACK FLOW DÉTECTÉ (Écoulement libre)")
            self.lbl_statut.setStyleSheet("font-size: 18px; font-weight: bold; color: #cc0000;")
        elif self.current_inj == 0:
            self.lbl_statut.setText("STATUT : MODE PRÉDICTION (Pompes à l'arrêt)")
            self.lbl_statut.setStyleSheet("font-size: 18px; font-weight: bold; color: #b45f06;")
        elif self.current_inj == 1:
            self.lbl_statut.setText(f"STATUT : INJECTION EAU (Débit: {Q_act} m3/h)")
            self.lbl_statut.setStyleSheet("font-size: 18px; font-weight: bold; color: blue;")
        elif self.current_inj == 2:
            self.lbl_statut.setText(f"STATUT : INJECTION PULPE (Densité: {densite_tete} kg/m3)")
            self.lbl_statut.setStyleSheet("font-size: 18px; font-weight: bold; color: darkorange;")
            
        self.line_hgl.set_ydata(HGL)
        self.scatter_fluids.set_color(colors)
        self.canvas.draw()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre = SimulateurSCADA()
    fenetre.show()
    sys.exit(app.exec_())