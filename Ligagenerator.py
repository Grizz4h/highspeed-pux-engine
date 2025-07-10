# -*- coding: utf-8 -*-
"""DEL‑Style Eishockey‑Liga‑Simulation
-------------------------------------------------
• Zwei Conferences (Nord/Süd) mit einfachem Double‑Round‑Robin und Play‑offs
• Scorer‑Tabelle auf Spieler‑Ebene
• Save‑/Load‑Funktion (JSON) für Spielfortschritt

👉 Füge deine Team‑Daten in die Listen `nord_teams` und `sued_teams` ein (vgl. Beispiel) 👈
"""

import os
import json
import random
import pandas as pd

# 1. ---------------- SAVE / LOAD ----------------

def save_progress(filename: str, data: dict) -> None:
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_progress(filename: str):
    if os.path.exists(filename) and os.path.getsize(filename) > 0:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# 2. ---------------- TEAMS (Beispiel‑Struktur) ----------------

nord_teams = [
    {"Team": "Berlin EisBären", "Players": [
    {"Name": "Jako Hildran", "Offense": 42, "Defense": 80, "Speed": 55, "Chemistry": 68},
    {"Name": "Jon Stetvik", "Offense": 38, "Defense": 75, "Speed": 54, "Chemistry": 66},
    {"Name": "Anto Brandik", "Offense": 35, "Defense": 73, "Speed": 53, "Chemistry": 65},
    {"Name": "Lino Veylar", "Offense": 36, "Defense": 72, "Speed": 52, "Chemistry": 64},
    {"Name": "Adan Smitrov", "Offense": 60, "Defense": 74, "Speed": 64, "Chemistry": 68},
    {"Name": "Mitch Reinov", "Offense": 62, "Defense": 73, "Speed": 66, "Chemistry": 69},
    {"Name": "Kai Vismann", "Offense": 65, "Defense": 76, "Speed": 67, "Chemistry": 70},
    {"Name": "Er Mikov", "Offense": 58, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Jon Mullerik", "Offense": 64, "Defense": 75, "Speed": 65, "Chemistry": 69},
    {"Name": "Korb Geibrov", "Offense": 59, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Oliv Galipek", "Offense": 61, "Defense": 71, "Speed": 64, "Chemistry": 67},
    {"Name": "Mark Niemelov", "Offense": 66, "Defense": 77, "Speed": 68, "Chemistry": 70},
    {"Name": "Nor Panok", "Offense": 55, "Defense": 69, "Speed": 61, "Chemistry": 65},
    {"Name": "Ty Ronnvik", "Offense": 78, "Defense": 62, "Speed": 74, "Chemistry": 72},
    {"Name": "Len Bergvik", "Offense": 70, "Defense": 65, "Speed": 70, "Chemistry": 69},
    {"Name": "Man Wiedran", "Offense": 68, "Defense": 64, "Speed": 69, "Chemistry": 68},
    {"Name": "Blan Byrik", "Offense": 74, "Defense": 63, "Speed": 72, "Chemistry": 70},
    {"Name": "Mat Lednov", "Offense": 66, "Defense": 61, "Speed": 68, "Chemistry": 67},
    {"Name": "Yan Veilov", "Offense": 72, "Defense": 62, "Speed": 70, "Chemistry": 69},
    {"Name": "Max Schafrik", "Offense": 64, "Defense": 60, "Speed": 67, "Chemistry": 67},
    {"Name": "Er Hordvik", "Offense": 63, "Defense": 61, "Speed": 66, "Chemistry": 66},
    {"Name": "Mich Bartov", "Offense": 62, "Defense": 59, "Speed": 65, "Chemistry": 66},
    {"Name": "Eli Scheinik", "Offense": 61, "Defense": 58, "Speed": 65, "Chemistry": 65},
    {"Name": "Zach Boychov", "Offense": 75, "Defense": 63, "Speed": 71, "Chemistry": 70},
    {"Name": "Mar Noeblen", "Offense": 77, "Defense": 64, "Speed": 72, "Chemistry": 71},
    {"Name": "Leo Pfoedrik", "Offense": 76, "Defense": 65, "Speed": 73, "Chemistry": 71},
    {"Name": "Lian Kirvik", "Offense": 69, "Defense": 62, "Speed": 69, "Chemistry": 68},
    {"Name": "Fred Tiffelov", "Offense": 71, "Defense": 63, "Speed": 70, "Chemistry": 69},
    {"Name": "Gab Fontanov", "Offense": 68, "Defense": 61, "Speed": 68, "Chemistry": 67}
    ], "Momentum": 0},
    {"Team": "Bremerhaven Forge", "Players": [
    {"Name": "Krist Gudlavik", "Offense": 42, "Defense": 80, "Speed": 55, "Chemistry": 68},
    {"Name": "Max Franzen", "Offense": 40, "Defense": 76, "Speed": 54, "Chemistry": 66},
    {"Name": "Seb Grafen", "Offense": 36, "Defense": 73, "Speed": 53, "Chemistry": 65},
    {"Name": "Mat Lowen", "Offense": 35, "Defense": 71, "Speed": 52, "Chemistry": 64},
    {"Name": "And Grovik", "Offense": 62, "Defense": 77, "Speed": 66, "Chemistry": 70},
    {"Name": "Ray Bettan", "Offense": 55, "Defense": 69, "Speed": 63, "Chemistry": 66},
    {"Name": "Lud Bystrom", "Offense": 58, "Defense": 72, "Speed": 65, "Chemistry": 68},
    {"Name": "Vlad Eminov", "Offense": 60, "Defense": 70, "Speed": 64, "Chemistry": 67},
    {"Name": "Niko Appendik", "Offense": 65, "Defense": 68, "Speed": 68, "Chemistry": 69},
    {"Name": "Matt Abtek", "Offense": 59, "Defense": 71, "Speed": 62, "Chemistry": 67},
    {"Name": "Nick Jensik", "Offense": 63, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Max Rauskin", "Offense": 61, "Defense": 69, "Speed": 66, "Chemistry": 66},
    {"Name": "Phil Brugsen", "Offense": 57, "Defense": 67, "Speed": 61, "Chemistry": 65},
    {"Name": "Nino Kindrik", "Offense": 68, "Defense": 60, "Speed": 69, "Chemistry": 67},
    {"Name": "Jan Urbenko", "Offense": 75, "Defense": 63, "Speed": 72, "Chemistry": 70},
    {"Name": "Zig Jeglov", "Offense": 74, "Defense": 62, "Speed": 71, "Chemistry": 69},
    {"Name": "Ros Maurik", "Offense": 73, "Defense": 61, "Speed": 70, "Chemistry": 68},
    {"Name": "Mar Khairin", "Offense": 66, "Defense": 59, "Speed": 68, "Chemistry": 66},
    {"Name": "Max Goertik", "Offense": 70, "Defense": 61, "Speed": 70, "Chemistry": 68},
    {"Name": "Fab Herrik", "Offense": 64, "Defense": 58, "Speed": 66, "Chemistry": 66},
    {"Name": "Dom Uhren", "Offense": 72, "Defense": 62, "Speed": 71, "Chemistry": 69},
    {"Name": "Marl Quinov", "Offense": 69, "Defense": 60, "Speed": 70, "Chemistry": 68},
    {"Name": "Mark Vikstad", "Offense": 71, "Defense": 61, "Speed": 71, "Chemistry": 69},
    {"Name": "Fel Maegard", "Offense": 65, "Defense": 59, "Speed": 67, "Chemistry": 67},
    {"Name": "Alex Frison", "Offense": 68, "Defense": 60, "Speed": 68, "Chemistry": 68},
    {"Name": "Chris Wejsen", "Offense": 67, "Defense": 59, "Speed": 67, "Chemistry": 67},
    {"Name": "Ced Schemik", "Offense": 66, "Defense": 58, "Speed": 66, "Chemistry": 66},
    {"Name": "Jus Buesen", "Offense": 63, "Defense": 57, "Speed": 65, "Chemistry": 65},
    {"Name": "Mih Verlik", "Offense": 74, "Defense": 62, "Speed": 71, "Chemistry": 69}
    ], "Momentum": 0},
    {"Team": "Frankfurt Core", "Players": [
    {"Name": "Tom Grevvik", "Offense": 40, "Defense": 80, "Speed": 54, "Chemistry": 68},
    {"Name": "Juh Olkinov", "Offense": 42, "Defense": 78, "Speed": 55, "Chemistry": 69},
    {"Name": "Cod Brenik", "Offense": 38, "Defense": 75, "Speed": 53, "Chemistry": 66},
    {"Name": "Rod Shumakov", "Offense": 35, "Defense": 73, "Speed": 52, "Chemistry": 65},
    {"Name": "Reid McNelov", "Offense": 58, "Defense": 74, "Speed": 62, "Chemistry": 67},
    {"Name": "Kev Maginov", "Offense": 60, "Defense": 73, "Speed": 63, "Chemistry": 68},
    {"Name": "Mark Laurik", "Offense": 62, "Defense": 75, "Speed": 64, "Chemistry": 69},
    {"Name": "Phil Bidan", "Offense": 55, "Defense": 68, "Speed": 61, "Chemistry": 65},
    {"Name": "Max Matuskin", "Offense": 64, "Defense": 72, "Speed": 65, "Chemistry": 68},
    {"Name": "Lua Nievik", "Offense": 52, "Defense": 66, "Speed": 60, "Chemistry": 64},
    {"Name": "Dan Wirten", "Offense": 57, "Defense": 69, "Speed": 62, "Chemistry": 66},
    {"Name": "And Welinov", "Offense": 61, "Defense": 71, "Speed": 64, "Chemistry": 67},
    {"Name": "Nath Burnik", "Offense": 68, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Cart Profkin", "Offense": 70, "Defense": 61, "Speed": 69, "Chemistry": 68},
    {"Name": "Cart Rowson", "Offense": 75, "Defense": 63, "Speed": 71, "Chemistry": 70},
    {"Name": "Dens Lobik", "Offense": 63, "Defense": 58, "Speed": 65, "Chemistry": 66},
    {"Name": "Seb Cimmerik", "Offense": 61, "Defense": 57, "Speed": 64, "Chemistry": 65},
    {"Name": "Mark Schweik", "Offense": 60, "Defense": 56, "Speed": 63, "Chemistry": 64},
    {"Name": "Lin Froberg", "Offense": 72, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Jul Napravik", "Offense": 67, "Defense": 59, "Speed": 67, "Chemistry": 66},
    {"Name": "Dan Pfafgut", "Offense": 65, "Defense": 58, "Speed": 66, "Chemistry": 66},
    {"Name": "Dom Bokkan", "Offense": 74, "Defense": 61, "Speed": 71, "Chemistry": 69},
    {"Name": "Erik Browik", "Offense": 68, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Kev Bickar", "Offense": 62, "Defense": 57, "Speed": 64, "Chemistry": 65},
    {"Name": "Kris Wilkov", "Offense": 69, "Defense": 59, "Speed": 67, "Chemistry": 66},
    {"Name": "Cam Bracen", "Offense": 70, "Defense": 60, "Speed": 69, "Chemistry": 67}
    ], "Momentum": 0},
    {"Team": "Iserlohn Miners", "Players": [
    {"Name": "Hend Hanek", "Offense": 40, "Defense": 78, "Speed": 54, "Chemistry": 68},
    {"Name": "Fin Beckson", "Offense": 38, "Defense": 75, "Speed": 54, "Chemistry": 66},
    {"Name": "Ol Blumvik", "Offense": 35, "Defense": 73, "Speed": 53, "Chemistry": 65},
    {"Name": "Andre Jenikov", "Offense": 42, "Defense": 79, "Speed": 55, "Chemistry": 68},
    {"Name": "Zach Osbren", "Offense": 58, "Defense": 73, "Speed": 63, "Chemistry": 67},
    {"Name": "Hub Labrov", "Offense": 60, "Defense": 74, "Speed": 63, "Chemistry": 68},
    {"Name": "Emil Quarnik", "Offense": 62, "Defense": 75, "Speed": 64, "Chemistry": 69},
    {"Name": "Brand Gormov", "Offense": 64, "Defense": 76, "Speed": 65, "Chemistry": 69},
    {"Name": "Jo Hussvik", "Offense": 57, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Mari Bauken", "Offense": 55, "Defense": 68, "Speed": 61, "Chemistry": 65},
    {"Name": "Stan Dietrov", "Offense": 65, "Defense": 76, "Speed": 65, "Chemistry": 69},
    {"Name": "Colt Jobkin", "Offense": 59, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Col Ugben", "Offense": 56, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Dan Geigrov", "Offense": 60, "Defense": 60, "Speed": 66, "Chemistry": 66},
    {"Name": "Shan Gersov", "Offense": 70, "Defense": 63, "Speed": 71, "Chemistry": 68},
    {"Name": "Tyl Bolik", "Offense": 68, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Mac Rutkov", "Offense": 65, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Nol Saffrik", "Offense": 63, "Defense": 58, "Speed": 66, "Chemistry": 66},
    {"Name": "Eric Cornik", "Offense": 72, "Defense": 65, "Speed": 71, "Chemistry": 69},
    {"Name": "Jake Virtanov", "Offense": 75, "Defense": 66, "Speed": 72, "Chemistry": 70},
    {"Name": "Max Brunnik", "Offense": 61, "Defense": 59, "Speed": 67, "Chemistry": 66},
    {"Name": "Jon Brovik", "Offense": 62, "Defense": 60, "Speed": 67, "Chemistry": 66},
    {"Name": "Len Nielvik", "Offense": 60, "Defense": 58, "Speed": 65, "Chemistry": 65},
    {"Name": "Chris Thomik", "Offense": 70, "Defense": 62, "Speed": 69, "Chemistry": 68},
    {"Name": "Bray Burkov", "Offense": 71, "Defense": 63, "Speed": 70, "Chemistry": 68},
    {"Name": "Sven Ziegrov", "Offense": 67, "Defense": 61, "Speed": 68, "Chemistry": 67},
    {"Name": "Manu Albenk", "Offense": 64, "Defense": 60, "Speed": 66, "Chemistry": 66},
    {"Name": "Brand Trockik", "Offense": 69, "Defense": 62, "Speed": 69, "Chemistry": 67},
    {"Name": "Leo Bussov", "Offense": 60, "Defense": 58, "Speed": 65, "Chemistry": 65},
    {"Name": "Tar Jentzov", "Offense": 66, "Defense": 60, "Speed": 67, "Chemistry": 67},
    {"Name": "Mike Dalcol", "Offense": 73, "Defense": 64, "Speed": 71, "Chemistry": 69}
    ], "Momentum": 0},
    {"Team": "Köln Blitzhaie", "Players": [
    {"Name": "Mirk Pantov", "Offense": 40, "Defense": 78, "Speed": 54, "Chemistry": 68},
    {"Name": "Juli Hudakov", "Offense": 42, "Defense": 79, "Speed": 55, "Chemistry": 69},
    {"Name": "Tobi Ancik", "Offense": 38, "Defense": 75, "Speed": 53, "Chemistry": 66},
    {"Name": "Den Dojen", "Offense": 35, "Defense": 72, "Speed": 52, "Chemistry": 65},
    {"Name": "Luk Stuhrik", "Offense": 36, "Defense": 71, "Speed": 52, "Chemistry": 64},
    {"Name": "Jan Senhenk", "Offense": 58, "Defense": 73, "Speed": 63, "Chemistry": 67},
    {"Name": "Max Glotzen", "Offense": 60, "Defense": 74, "Speed": 63, "Chemistry": 68},
    {"Name": "Vel Vittanov", "Offense": 62, "Defense": 75, "Speed": 64, "Chemistry": 69},
    {"Name": "Ot Rantakov", "Offense": 64, "Defense": 76, "Speed": 65, "Chemistry": 69},
    {"Name": "Ad Almvik", "Offense": 61, "Defense": 71, "Speed": 64, "Chemistry": 67},
    {"Name": "Ed Tropov", "Offense": 55, "Defense": 69, "Speed": 61, "Chemistry": 65},
    {"Name": "Brad Austik", "Offense": 63, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "No Munzenk", "Offense": 57, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Mat Papov", "Offense": 56, "Defense": 68, "Speed": 61, "Chemistry": 65},
    {"Name": "Mor Mullov", "Offense": 65, "Defense": 76, "Speed": 65, "Chemistry": 69},
    {"Name": "Nik Lunenko", "Offense": 59, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Rob Calstern", "Offense": 66, "Defense": 60, "Speed": 67, "Chemistry": 67},
    {"Name": "Max Kammrik", "Offense": 72, "Defense": 62, "Speed": 71, "Chemistry": 69},
    {"Name": "Just Schutzen", "Offense": 75, "Defense": 63, "Speed": 72, "Chemistry": 70},
    {"Name": "Lou Aubren", "Offense": 74, "Defense": 62, "Speed": 71, "Chemistry": 69},
    {"Name": "Jos Currik", "Offense": 70, "Defense": 61, "Speed": 70, "Chemistry": 68},
    {"Name": "Fred Stormvik", "Offense": 77, "Defense": 64, "Speed": 72, "Chemistry": 71},
    {"Name": "Juha Tyrvain", "Offense": 73, "Defense": 62, "Speed": 71, "Chemistry": 69},
    {"Name": "Tim Wohlgard", "Offense": 71, "Defense": 63, "Speed": 70, "Chemistry": 68},
    {"Name": "Eli Lindvik", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Kev Niedik", "Offense": 65, "Defense": 60, "Speed": 67, "Chemistry": 66},
    {"Name": "Park Tuomik", "Offense": 69, "Defense": 61, "Speed": 70, "Chemistry": 68},
    {"Name": "Marc Munzenk", "Offense": 64, "Defense": 59, "Speed": 66, "Chemistry": 66},
    {"Name": "Alex Grennov", "Offense": 74, "Defense": 62, "Speed": 71, "Chemistry": 69},
    {"Name": "Greg Maclov", "Offense": 72, "Defense": 61, "Speed": 70, "Chemistry": 68},
    {"Name": "Hak Haenel", "Offense": 66, "Defense": 60, "Speed": 67, "Chemistry": 67}
    ], "Momentum": 0},
    {"Team": "Wolfsburg Voltsturm", "Players": [
    {"Name": "Dust Strahlov", "Offense": 42, "Defense": 79, "Speed": 55, "Chemistry": 68},
    {"Name": "Luc Erdvik", "Offense": 38, "Defense": 75, "Speed": 53, "Chemistry": 66},
    {"Name": "En Albrov", "Offense": 39, "Defense": 76, "Speed": 54, "Chemistry": 67},
    {"Name": "Han Weitzik", "Offense": 40, "Defense": 77, "Speed": 54, "Chemistry": 67},
    {"Name": "Jon Ramik", "Offense": 60, "Defense": 73, "Speed": 63, "Chemistry": 67},
    {"Name": "Bjo Kruvik", "Offense": 62, "Defense": 74, "Speed": 64, "Chemistry": 68},
    {"Name": "Rya Oconvik", "Offense": 64, "Defense": 75, "Speed": 65, "Chemistry": 69},
    {"Name": "Jan Mosrik", "Offense": 61, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Jim Martovik", "Offense": 58, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Jul Melkov", "Offense": 63, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Rya Butovik", "Offense": 59, "Defense": 71, "Speed": 63, "Chemistry": 67},
    {"Name": "Fab Pfohlik", "Offense": 57, "Defense": 69, "Speed": 62, "Chemistry": 66},
    {"Name": "Jim Lambrov", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Luc Dumov", "Offense": 66, "Defense": 60, "Speed": 67, "Chemistry": 66},
    {"Name": "Tan Kaspov", "Offense": 70, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Rob Vebrik", "Offense": 64, "Defense": 59, "Speed": 66, "Chemistry": 66},
    {"Name": "Ger Fausik", "Offense": 67, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Dar Archik", "Offense": 72, "Defense": 63, "Speed": 70, "Chemistry": 68},
    {"Name": "Phil Varnik", "Offense": 71, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Nick Caamov", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Jul Chrovik", "Offense": 63, "Defense": 58, "Speed": 66, "Chemistry": 66},
    {"Name": "Jul Ramovik", "Offense": 62, "Defense": 58, "Speed": 65, "Chemistry": 65},
    {"Name": "And Mielik", "Offense": 70, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Lui Schinkov", "Offense": 61, "Defense": 58, "Speed": 65, "Chemistry": 65},
    {"Name": "Jus Fesrik", "Offense": 68, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Tim Ruckik", "Offense": 60, "Defense": 57, "Speed": 65, "Chemistry": 65},
    {"Name": "Spen Machik", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Matt Whitov", "Offense": 74, "Defense": 62, "Speed": 71, "Chemistry": 69}
    ], "Momentum": 0},
    {"Team": "Krefeld Kernschlag", "Players": [
    {"Name": "Fel Bickov", "Offense": 40, "Defense": 79, "Speed": 55, "Chemistry": 68},
    {"Name": "Jul Schultik", "Offense": 38, "Defense": 75, "Speed": 53, "Chemistry": 66},
    {"Name": "Max Adamov", "Offense": 61, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Erik Buschik", "Offense": 59, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Zac Dybowik", "Offense": 58, "Defense": 69, "Speed": 62, "Chemistry": 66},
    {"Name": "Car Konzik", "Offense": 60, "Defense": 71, "Speed": 63, "Chemistry": 67},
    {"Name": "Mic Köhlov", "Offense": 62, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Ste Raabik", "Offense": 57, "Defense": 69, "Speed": 62, "Chemistry": 66},
    {"Name": "Dav Vandanov", "Offense": 63, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Dan Bruchov", "Offense": 64, "Defense": 59, "Speed": 66, "Chemistry": 66},
    {"Name": "Dav Cernik", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Nic Fockik", "Offense": 65, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Max Hopsik", "Offense": 66, "Defense": 60, "Speed": 67, "Chemistry": 66},
    {"Name": "Phil Kuhnov", "Offense": 67, "Defense": 61, "Speed": 68, "Chemistry": 67},
    {"Name": "Jon Matsov", "Offense": 70, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Roo Makitov", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Mar Mullerov", "Offense": 72, "Defense": 63, "Speed": 70, "Chemistry": 68},
    {"Name": "Max Newtov", "Offense": 71, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Mat Santov", "Offense": 70, "Defense": 62, "Speed": 69, "Chemistry": 68},
    {"Name": "Tim Schuzik", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Alex Weisvik", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Mark Zengerik", "Offense": 70, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Leon Korvik", "Offense": 61, "Defense": 59, "Speed": 67, "Chemistry": 66},
    {"Name": "Ol Mebov", "Offense": 60, "Defense": 58, "Speed": 66, "Chemistry": 66}
    ], "Momentum": 0},
    {"Team": "Düsseldorfer Aurora", "Players": [
    {"Name": "Leo Humrik", "Offense": 39, "Defense": 75, "Speed": 54, "Chemistry": 67},
    {"Name": "Kev Magrik", "Offense": 62, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Ry Olsev", "Offense": 71, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Kev Orendrik", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Col Smithov", "Offense": 72, "Defense": 63, "Speed": 71, "Chemistry": 68},
    {"Name": "Erik Bradov", "Offense": 70, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Nik Lunov", "Offense": 65, "Defense": 60, "Speed": 67, "Chemistry": 66}
    ], "Momentum": 0},
    {"Team": "Kassel Zenith", "Players": [
    {"Name": "Bran Maxvik", "Offense": 42, "Defense": 79, "Speed": 55, "Chemistry": 68},
    {"Name": "Phil Maurik", "Offense": 40, "Defense": 77, "Speed": 54, "Chemistry": 67},
    {"Name": "Tim Bendrov", "Offense": 60, "Defense": 73, "Speed": 63, "Chemistry": 67},
    {"Name": "And Bodnov", "Offense": 62, "Defense": 74, "Speed": 64, "Chemistry": 68},
    {"Name": "Mark Frevik", "Offense": 58, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Sim Schutzik", "Offense": 63, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Bod Wildrik", "Offense": 61, "Defense": 71, "Speed": 63, "Chemistry": 67},
    {"Name": "Ale Ahlrik", "Offense": 67, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Lau Braunik", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Han Detskov", "Offense": 65, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Hun Garlov", "Offense": 71, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Tris Keckov", "Offense": 72, "Defense": 63, "Speed": 71, "Chemistry": 69},
    {"Name": "Dar Mieskov", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Mac Rutkov", "Offense": 66, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Dom Turgov", "Offense": 70, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Yan Valentik", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Jak Weidrik", "Offense": 67, "Defense": 61, "Speed": 69, "Chemistry": 67}
    ], "Momentum": 0},
    {"Team": "Bad Nauheim Ferox", "Players": [
    {"Name": "Fin Beckov", "Offense": 40, "Defense": 77, "Speed": 54, "Chemistry": 67},
    {"Name": "Ger Kuhnov", "Offense": 42, "Defense": 79, "Speed": 55, "Chemistry": 68},
    {"Name": "Mar Erkov", "Offense": 60, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Chris Fischrik", "Offense": 62, "Defense": 74, "Speed": 64, "Chemistry": 68},
    {"Name": "Sim Gnypov", "Offense": 58, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Gar Prudov", "Offense": 63, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Pat Seifrik", "Offense": 61, "Defense": 71, "Speed": 63, "Chemistry": 67},
    {"Name": "Park Bowlik", "Offense": 74, "Defense": 63, "Speed": 71, "Chemistry": 69},
    {"Name": "Marc Elsayev", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Jord Hickov", "Offense": 72, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Zac Kaisov", "Offense": 67, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Dav Kochik", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Jul Lautrik", "Offense": 66, "Defense": 60, "Speed": 67, "Chemistry": 66},
    {"Name": "Tay Vausik", "Offense": 68, "Defense": 61, "Speed": 68, "Chemistry": 67},
    {"Name": "Jus Volevik", "Offense": 65, "Defense": 60, "Speed": 67, "Chemistry": 66}
    ], "Momentum": 0},
    # ➡️ weitere Nord Teams
]

sued_teams = [
    {"Team": "Ingolstadt Indigo Panther", "Players": [
    {"Name": "Niko Pertanov", "Offense": 35, "Defense": 70, "Speed": 50, "Chemistry": 60},
    {"Name": "Devon Willark", "Offense": 40, "Defense": 75, "Speed": 55, "Chemistry": 65},
    {"Name": "Bret Brokan", "Offense": 45, "Defense": 78, "Speed": 60, "Chemistry": 68},
    {"Name": "Sam Ruvek", "Offense": 62, "Defense": 80, "Speed": 65, "Chemistry": 72},
    {"Name": "Morgon Elvik", "Offense": 65, "Defense": 77, "Speed": 63, "Chemistry": 70},
    {"Name": "Leo Hütten", "Offense": 60, "Defense": 70, "Speed": 67, "Chemistry": 69},
    {"Name": "Aleks Bretan", "Offense": 72, "Defense": 73, "Speed": 69, "Chemistry": 73},
    {"Name": "Petr Spornik", "Offense": 58, "Defense": 69, "Speed": 65, "Chemistry": 66},
    {"Name": "Kris Jandro", "Offense": 61, "Defense": 71, "Speed": 66, "Chemistry": 68},
    {"Name": "Edwin Tropov", "Offense": 55, "Defense": 67, "Speed": 62, "Chemistry": 65},
    {"Name": "Filip Krausen", "Offense": 70, "Defense": 65, "Speed": 74, "Chemistry": 70},
    {"Name": "Mils Powlek", "Offense": 75, "Defense": 60, "Speed": 76, "Chemistry": 72},
    {"Name": "Ken Agostinov", "Offense": 80, "Defense": 62, "Speed": 75, "Chemistry": 74},
    {"Name": "Johan Krausen", "Offense": 68, "Defense": 63, "Speed": 70, "Chemistry": 68},
    {"Name": "Abbo Girdunov", "Offense": 77, "Defense": 64, "Speed": 73, "Chemistry": 72},
    {"Name": "Charl Bertraux", "Offense": 82, "Defense": 60, "Speed": 74, "Chemistry": 73},
    {"Name": "Enrik Henrova", "Offense": 65, "Defense": 58, "Speed": 68, "Chemistry": 66},
    {"Name": "Luka Hauven", "Offense": 67, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Dan Pietto", "Offense": 72, "Defense": 66, "Speed": 65, "Chemistry": 70},
    {"Name": "Aust Keaten", "Offense": 74, "Defense": 62, "Speed": 71, "Chemistry": 69},
    {"Name": "Rilan Barvik", "Offense": 79, "Defense": 63, "Speed": 75, "Chemistry": 72},
    {"Name": "Dano Schmolik", "Offense": 73, "Defense": 64, "Speed": 70, "Chemistry": 70},
    {"Name": "Sam Kharbintli", "Offense": 66, "Defense": 59, "Speed": 67, "Chemistry": 65},
    {"Name": "Eli Pulsen", "Offense": 63, "Defense": 57, "Speed": 66, "Chemistry": 64}
    ], "Momentum": 0},
    {"Team": "Augsburg Ferox", "Players": [
    {"Name": "Mikel Gartik", "Offense": 38, "Defense": 78, "Speed": 53, "Chemistry": 68},
    {"Name": "Madis Bovik", "Offense": 62, "Defense": 77, "Speed": 66, "Chemistry": 70},
    {"Name": "Seb Zwicklo", "Offense": 55, "Defense": 69, "Speed": 63, "Chemistry": 66},
    {"Name": "Moriz Wirthan", "Offense": 58, "Defense": 72, "Speed": 65, "Chemistry": 68},
    {"Name": "Leo Vandlin", "Offense": 60, "Defense": 70, "Speed": 64, "Chemistry": 67},
    {"Name": "Nolo Zajak", "Offense": 65, "Defense": 68, "Speed": 68, "Chemistry": 69},
    {"Name": "Max Rennik", "Offense": 59, "Defense": 71, "Speed": 62, "Chemistry": 67},
    {"Name": "Tom Schevik", "Offense": 63, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Rilo McKurt", "Offense": 61, "Defense": 69, "Speed": 66, "Chemistry": 66},
    {"Name": "Nik Grassik", "Offense": 57, "Defense": 67, "Speed": 61, "Chemistry": 65},
    {"Name": "Kon Fiedran", "Offense": 56, "Defense": 66, "Speed": 62, "Chemistry": 65},
    {"Name": "Alex Grenno", "Offense": 75, "Defense": 62, "Speed": 72, "Chemistry": 71},
    {"Name": "Seb Zwinko", "Offense": 60, "Defense": 60, "Speed": 65, "Chemistry": 66},
    {"Name": "Alex Blanko", "Offense": 70, "Defense": 63, "Speed": 71, "Chemistry": 68},
    {"Name": "Tim Wohlgard", "Offense": 72, "Defense": 65, "Speed": 70, "Chemistry": 69},
    {"Name": "Kris Collen", "Offense": 73, "Defense": 61, "Speed": 73, "Chemistry": 70},
    {"Name": "Don Busdek", "Offense": 68, "Defense": 60, "Speed": 69, "Chemistry": 67},
    {"Name": "Anton Louvis", "Offense": 74, "Defense": 62, "Speed": 72, "Chemistry": 70},
    {"Name": "Rilo Damian", "Offense": 71, "Defense": 61, "Speed": 71, "Chemistry": 69},
    {"Name": "Kody Kunak", "Offense": 69, "Defense": 60, "Speed": 70, "Chemistry": 68},
    {"Name": "Tom Trevik", "Offense": 65, "Defense": 59, "Speed": 68, "Chemistry": 67},
    {"Name": "Chris Hanken", "Offense": 64, "Defense": 58, "Speed": 66, "Chemistry": 66},
    {"Name": "Moriz Elian", "Offense": 62, "Defense": 57, "Speed": 65, "Chemistry": 65},
    {"Name": "Flor Elian", "Offense": 63, "Defense": 58, "Speed": 66, "Chemistry": 66},
    {"Name": "Niko Baptik", "Offense": 74, "Defense": 61, "Speed": 72, "Chemistry": 70},
    {"Name": "Luka Tosten", "Offense": 61, "Defense": 59, "Speed": 65, "Chemistry": 66},
    {"Name": "Mark Zenger", "Offense": 68, "Defense": 60, "Speed": 68, "Chemistry": 68},
    {"Name": "Anre Hakulin", "Offense": 66, "Defense": 59, "Speed": 67, "Chemistry": 67},
    {"Name": "Mik Kohlan", "Offense": 60, "Defense": 58, "Speed": 64, "Chemistry": 65}
    ], "Momentum": 0},
    {"Team": "Mannheim Ventus", "Players": [
    {"Name": "Alex Gravik", "Offense": 42, "Defense": 80, "Speed": 55, "Chemistry": 68},
    {"Name": "Arn Tiefenov", "Offense": 40, "Defense": 78, "Speed": 54, "Chemistry": 67},
    {"Name": "Leo Willik", "Offense": 38, "Defense": 75, "Speed": 53, "Chemistry": 66},
    {"Name": "Fel Brukov", "Offense": 45, "Defense": 79, "Speed": 56, "Chemistry": 69},
    {"Name": "Nik Cicekov", "Offense": 60, "Defense": 73, "Speed": 63, "Chemistry": 67},
    {"Name": "Tob Fohrik", "Offense": 62, "Defense": 74, "Speed": 64, "Chemistry": 68},
    {"Name": "Jon Gilmov", "Offense": 64, "Defense": 75, "Speed": 65, "Chemistry": 69},
    {"Name": "Leo Gawik", "Offense": 66, "Defense": 76, "Speed": 66, "Chemistry": 70},
    {"Name": "Jyr Jokipaak", "Offense": 65, "Defense": 75, "Speed": 65, "Chemistry": 69},
    {"Name": "Zac Leskov", "Offense": 63, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Tim Lovrik", "Offense": 61, "Defense": 71, "Speed": 63, "Chemistry": 67},
    {"Name": "Luk Kalben", "Offense": 62, "Defense": 72, "Speed": 64, "Chemistry": 67},
    {"Name": "Pal Mayrov", "Offense": 58, "Defense": 69, "Speed": 62, "Chemistry": 66},
    {"Name": "Fab Pilun", "Offense": 59, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Aust Ortegik", "Offense": 75, "Defense": 62, "Speed": 73, "Chemistry": 70},
    {"Name": "Kris Reichov", "Offense": 72, "Defense": 63, "Speed": 71, "Chemistry": 69},
    {"Name": "Stef Loiben", "Offense": 74, "Defense": 64, "Speed": 72, "Chemistry": 70},
    {"Name": "Jord Szvarik", "Offense": 73, "Defense": 63, "Speed": 71, "Chemistry": 69},
    {"Name": "Eric Ubanov", "Offense": 68, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Luk Espozik", "Offense": 70, "Defense": 61, "Speed": 70, "Chemistry": 68},
    {"Name": "Kris Bennov", "Offense": 71, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Mat Plachtov", "Offense": 74, "Defense": 63, "Speed": 71, "Chemistry": 69},
    {"Name": "Sam Soramov", "Offense": 67, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Yan Proskik", "Offense": 66, "Defense": 59, "Speed": 67, "Chemistry": 66},
    {"Name": "Mark Hennik", "Offense": 72, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Tom Kuhnov", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Dust Wilhof", "Offense": 61, "Defense": 58, "Speed": 66, "Chemistry": 66},
    {"Name": "Marc Michaelov", "Offense": 75, "Defense": 63, "Speed": 71, "Chemistry": 69},
    {"Name": "Dan Fischvik", "Offense": 68, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Rya Macinnov", "Offense": 73, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Max Heimrik", "Offense": 65, "Defense": 59, "Speed": 67, "Chemistry": 66}
    ], "Momentum": 0},
    {"Team": "München FluxBullen", "Players": [
    {"Name": "Math Niedrov", "Offense": 42, "Defense": 80, "Speed": 55, "Chemistry": 68},
    {"Name": "Ev Fitzpatov", "Offense": 40, "Defense": 78, "Speed": 54, "Chemistry": 67},
    {"Name": "Sim Wolvik", "Offense": 38, "Defense": 75, "Speed": 53, "Chemistry": 66},
    {"Name": "Dom Bittrov", "Offense": 60, "Defense": 73, "Speed": 63, "Chemistry": 67},
    {"Name": "Will Butchik", "Offense": 62, "Defense": 74, "Speed": 64, "Chemistry": 68},
    {"Name": "Kon Abelvik", "Offense": 65, "Defense": 75, "Speed": 65, "Chemistry": 69},
    {"Name": "Jak Webrov", "Offense": 58, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Jon Blumov", "Offense": 64, "Defense": 76, "Speed": 65, "Chemistry": 69},
    {"Name": "Sten Fischrik", "Offense": 59, "Defense": 71, "Speed": 63, "Chemistry": 67},
    {"Name": "Emil Johansk", "Offense": 63, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Max Daubrik", "Offense": 61, "Defense": 71, "Speed": 63, "Chemistry": 67},
    {"Name": "Les Lanstrik", "Offense": 62, "Defense": 72, "Speed": 64, "Chemistry": 67},
    {"Name": "Will Riedik", "Offense": 60, "Defense": 70, "Speed": 63, "Chemistry": 66},
    {"Name": "Tob Riedov", "Offense": 72, "Defense": 63, "Speed": 71, "Chemistry": 69},
    {"Name": "Mark Eisenshik", "Offense": 75, "Defense": 64, "Speed": 72, "Chemistry": 70},
    {"Name": "Ben Smithov", "Offense": 74, "Defense": 63, "Speed": 71, "Chemistry": 69},
    {"Name": "Nik Maulik", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Niko Heigrov", "Offense": 67, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Taro Hirovek", "Offense": 76, "Defense": 63, "Speed": 72, "Chemistry": 70},
    {"Name": "And Ederov", "Offense": 70, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Niko Kramrik", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Veit Oswalden", "Offense": 66, "Defense": 60, "Speed": 67, "Chemistry": 66},
    {"Name": "Yas Ehlivik", "Offense": 73, "Defense": 62, "Speed": 71, "Chemistry": 69},
    {"Name": "Pat Hagrov", "Offense": 71, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Adam Brovik", "Offense": 74, "Defense": 63, "Speed": 71, "Chemistry": 69},
    {"Name": "Chris Desovik", "Offense": 75, "Defense": 63, "Speed": 72, "Chemistry": 70},
    {"Name": "Fil Varejkik", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Max Kastrov", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Alex Blankov", "Offense": 70, "Defense": 62, "Speed": 70, "Chemistry": 68}
    ], "Momentum": 0},
    {"Team": "Nürnberg Eistiger", "Players": [
    {"Name": "Nik Treutov", "Offense": 42, "Defense": 79, "Speed": 55, "Chemistry": 68},
    {"Name": "Dan Allavik", "Offense": 40, "Defense": 77, "Speed": 54, "Chemistry": 67},
    {"Name": "Leo Hungrov", "Offense": 39, "Defense": 76, "Speed": 54, "Chemistry": 67},
    {"Name": "Jul Karrik", "Offense": 60, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Marc Webrov", "Offense": 62, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Ow Headrov", "Offense": 65, "Defense": 75, "Speed": 65, "Chemistry": 69},
    {"Name": "Cod Haiskov", "Offense": 63, "Defense": 74, "Speed": 64, "Chemistry": 68},
    {"Name": "Hay Shawrik", "Offense": 61, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Con Braunov", "Offense": 64, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Jus Bottik", "Offense": 58, "Defense": 69, "Speed": 62, "Chemistry": 66},
    {"Name": "Max Merklik", "Offense": 57, "Defense": 68, "Speed": 61, "Chemistry": 65},
    {"Name": "Evan Barrakov", "Offense": 75, "Defense": 63, "Speed": 72, "Chemistry": 70},
    {"Name": "Rya Stoavik", "Offense": 72, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Col Maiev", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Luk Ribaren", "Offense": 65, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Eug Alanik", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Jos Ehamov", "Offense": 64, "Defense": 59, "Speed": 67, "Chemistry": 66},
    {"Name": "Jak Ustrov", "Offense": 66, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Tom Heiglik", "Offense": 63, "Defense": 59, "Speed": 66, "Chemistry": 66},
    {"Name": "Rom Kechrik", "Offense": 62, "Defense": 58, "Speed": 65, "Chemistry": 65},
    {"Name": "Sam Dovik", "Offense": 67, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Will Grabov", "Offense": 70, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Jer Mckenik", "Offense": 71, "Defense": 63, "Speed": 71, "Chemistry": 69},
    {"Name": "Mar Rassik", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Char Gerardik", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67}
    ], "Momentum": 0},
    {"Team": "Schwenningen Sturmflügel", "Players": [
    {"Name": "Mike Bitzov", "Offense": 40, "Defense": 78, "Speed": 54, "Chemistry": 68},
    {"Name": "Joac Erikov", "Offense": 42, "Defense": 79, "Speed": 55, "Chemistry": 69},
    {"Name": "Jord Murik", "Offense": 62, "Defense": 75, "Speed": 65, "Chemistry": 69},
    {"Name": "Dar Boylen", "Offense": 61, "Defense": 74, "Speed": 64, "Chemistry": 68},
    {"Name": "Dan Schwik", "Offense": 58, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Ark Dziamov", "Offense": 60, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Tom Larkov", "Offense": 64, "Defense": 76, "Speed": 65, "Chemistry": 69},
    {"Name": "Alex Trivik", "Offense": 63, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Ben Marshik", "Offense": 59, "Defense": 71, "Speed": 63, "Chemistry": 67},
    {"Name": "Will Webrik", "Offense": 65, "Defense": 75, "Speed": 65, "Chemistry": 69},
    {"Name": "Phil Feistik", "Offense": 64, "Defense": 59, "Speed": 66, "Chemistry": 66},
    {"Name": "Mir Höffvik", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Vik Buchrik", "Offense": 62, "Defense": 58, "Speed": 66, "Chemistry": 66},
    {"Name": "Dan Neumov", "Offense": 60, "Defense": 57, "Speed": 65, "Chemistry": 65},
    {"Name": "Bret Richov", "Offense": 72, "Defense": 63, "Speed": 70, "Chemistry": 68},
    {"Name": "Ken Olimvik", "Offense": 70, "Defense": 62, "Speed": 69, "Chemistry": 68},
    {"Name": "Lou Majrik", "Offense": 61, "Defense": 58, "Speed": 65, "Chemistry": 65},
    {"Name": "Leo Bauvik", "Offense": 59, "Defense": 57, "Speed": 64, "Chemistry": 65},
    {"Name": "Alex Karakov", "Offense": 67, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Boaz Bassik", "Offense": 63, "Defense": 58, "Speed": 66, "Chemistry": 66},
    {"Name": "Bran McMillik", "Offense": 71, "Defense": 62, "Speed": 69, "Chemistry": 68},
    {"Name": "Matt Puempov", "Offense": 70, "Defense": 61, "Speed": 69, "Chemistry": 68},
    {"Name": "Kyl Platzik", "Offense": 69, "Defense": 61, "Speed": 68, "Chemistry": 67},
    {"Name": "Zach Senyk", "Offense": 73, "Defense": 63, "Speed": 70, "Chemistry": 68},
    {"Name": "Tyl Spinkov", "Offense": 72, "Defense": 62, "Speed": 69, "Chemistry": 68},
    {"Name": "Seb Uvirik", "Offense": 68, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Phil Hungrov", "Offense": 66, "Defense": 59, "Speed": 67, "Chemistry": 66},
    {"Name": "Tys Spinkov", "Offense": 74, "Defense": 63, "Speed": 71, "Chemistry": 69},
    {"Name": "Ste Majrik", "Offense": 60, "Defense": 57, "Speed": 65, "Chemistry": 65},
    {"Name": "Bar Cicekov", "Offense": 58, "Defense": 56, "Speed": 64, "Chemistry": 65}
    ], "Momentum": 0},
    {"Team": "Straubing Forest Tigers", "Players": [
    {"Name": "Flor Buglik", "Offense": 39, "Defense": 75, "Speed": 54, "Chemistry": 67},
    {"Name": "Zan McIntov", "Offense": 42, "Defense": 79, "Speed": 55, "Chemistry": 68},
    {"Name": "Pasc Seidrik", "Offense": 38, "Defense": 74, "Speed": 53, "Chemistry": 66},
    {"Name": "Nic Geitrov", "Offense": 58, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Alex Grennov", "Offense": 62, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Stef Daschik", "Offense": 61, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Mar Zimmerik", "Offense": 59, "Defense": 71, "Speed": 63, "Chemistry": 67},
    {"Name": "Ad Klenov", "Offense": 57, "Defense": 69, "Speed": 62, "Chemistry": 66},
    {"Name": "Phil Samulov", "Offense": 64, "Defense": 74, "Speed": 64, "Chemistry": 68},
    {"Name": "Jus Braunov", "Offense": 63, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Nels Nogrik", "Offense": 60, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Marc Brandov", "Offense": 65, "Defense": 75, "Speed": 65, "Chemistry": 69},
    {"Name": "Tay Leirik", "Offense": 70, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Josh Samanskik", "Offense": 67, "Defense": 60, "Speed": 68, "Chemistry": 67},
    {"Name": "Mich Clarkov", "Offense": 65, "Defense": 59, "Speed": 67, "Chemistry": 66},
    {"Name": "Tim Brunov", "Offense": 64, "Defense": 58, "Speed": 66, "Chemistry": 66},
    {"Name": "Just Scotrik", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Mich Connov", "Offense": 68, "Defense": 61, "Speed": 68, "Chemistry": 67},
    {"Name": "Josh Melnov", "Offense": 70, "Defense": 62, "Speed": 69, "Chemistry": 68},
    {"Name": "Dan Leonik", "Offense": 63, "Defense": 59, "Speed": 66, "Chemistry": 66},
    {"Name": "Lin Brandik", "Offense": 62, "Defense": 58, "Speed": 65, "Chemistry": 65},
    {"Name": "Trav Denisov", "Offense": 72, "Defense": 63, "Speed": 70, "Chemistry": 68},
    {"Name": "Elis Hedrik", "Offense": 61, "Defense": 58, "Speed": 65, "Chemistry": 65},
    {"Name": "Sky McKenzik", "Offense": 64, "Defense": 59, "Speed": 66, "Chemistry": 66},
    {"Name": "JC Liprik", "Offense": 71, "Defense": 62, "Speed": 69, "Chemistry": 68},
    {"Name": "Tim Fleishik", "Offense": 60, "Defense": 57, "Speed": 65, "Chemistry": 65}
    ], "Momentum": 0},
    {"Team": "Landshut Lichtkern", "Players": [
    {"Name": "Jon Langov", "Offense": 42, "Defense": 79, "Speed": 55, "Chemistry": 68},
    {"Name": "Phil Dietrov", "Offense": 40, "Defense": 77, "Speed": 54, "Chemistry": 67},
    {"Name": "Wad Bergov", "Offense": 61, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Alex Derschik", "Offense": 60, "Defense": 71, "Speed": 63, "Chemistry": 67},
    {"Name": "And Schwarzov", "Offense": 62, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Stan Dietrov", "Offense": 64, "Defense": 75, "Speed": 65, "Chemistry": 69},
    {"Name": "Seo Parkov", "Offense": 58, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Dav Elsnov", "Offense": 72, "Defense": 63, "Speed": 71, "Chemistry": 69},
    {"Name": "Tor Immov", "Offense": 71, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Jul Kornik", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Jes Koskov", "Offense": 70, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Tob Lindvik", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Jak Mayenov", "Offense": 67, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Pasc Stekov", "Offense": 65, "Defense": 60, "Speed": 67, "Chemistry": 66},
    {"Name": "Yan Wenzik", "Offense": 66, "Defense": 60, "Speed": 67, "Chemistry": 66},
    {"Name": "Luk Gausik", "Offense": 64, "Defense": 59, "Speed": 66, "Chemistry": 66},
    {"Name": "Lui Scheibrik", "Offense": 63, "Defense": 58, "Speed": 65, "Chemistry": 65},
    {"Name": "Mar Tabrov", "Offense": 62, "Defense": 58, "Speed": 65, "Chemistry": 65}
    ], "Momentum": 0},
    {"Team": "Regensburg Pulse", "Players": [
    {"Name": "Jon Neffrik", "Offense": 40, "Defense": 77, "Speed": 54, "Chemistry": 67},
    {"Name": "Guil Naudrik", "Offense": 61, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Pasc Zersov", "Offense": 62, "Defense": 73, "Speed": 64, "Chemistry": 68},
    {"Name": "Mar Baurov", "Offense": 58, "Defense": 70, "Speed": 62, "Chemistry": 66},
    {"Name": "Pat Demov", "Offense": 60, "Defense": 71, "Speed": 63, "Chemistry": 67},
    {"Name": "Sea Gilesik", "Offense": 59, "Defense": 71, "Speed": 63, "Chemistry": 67},
    {"Name": "Ale Angrik", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Luk Kriegov", "Offense": 66, "Defense": 60, "Speed": 67, "Chemistry": 66},
    {"Name": "Con Ontlov", "Offense": 67, "Defense": 61, "Speed": 68, "Chemistry": 67},
    {"Name": "Sam Payurik", "Offense": 65, "Defense": 60, "Speed": 67, "Chemistry": 66},
    {"Name": "Pier Pretov", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Cor Trivonov", "Offense": 72, "Defense": 63, "Speed": 71, "Chemistry": 69}
    ], "Momentum": 0},
    {"Team": "Ravensburg Zenith Falcons", "Players": [
    {"Name": "Ily Sharov", "Offense": 42, "Defense": 79, "Speed": 55, "Chemistry": 68},
    {"Name": "Sim Sezik", "Offense": 61, "Defense": 72, "Speed": 63, "Chemistry": 67},
    {"Name": "Rob Czarnov", "Offense": 72, "Defense": 63, "Speed": 71, "Chemistry": 69},
    {"Name": "Ans Gergov", "Offense": 66, "Defense": 60, "Speed": 67, "Chemistry": 66},
    {"Name": "Erik Karlov", "Offense": 70, "Defense": 62, "Speed": 70, "Chemistry": 68},
    {"Name": "Nick Lattik", "Offense": 68, "Defense": 61, "Speed": 69, "Chemistry": 67},
    {"Name": "Thom Reichik", "Offense": 69, "Defense": 61, "Speed": 69, "Chemistry": 67}
    ], "Momentum": 0},
    # ➡️ weitere Süd Teams
]


# 3. ---------------- ROUND‑ROBIN SCHEDULE ----------------

def create_round_robin_schedule(teams: list[dict]) -> list[tuple[str, str]]:
    """Erstellt einen doppelt‑rundigen Spielplan (Hin‑ & Rückspiel)."""
    t = teams.copy()
    if len(t) % 2:
        t.append({"Team": "BYE"})  # Dummy‑Team für ungerade Anzahl
    days = len(t) - 1
    half = len(t) // 2
    schedule: list[tuple[str, str]] = []
    for day in range(days * 2):
        pairs = []
        for i in range(half):
            home, away = t[i]["Team"], t[-i - 1]["Team"]
            pairs.append((home, away) if day % 2 == 0 else (away, home))
        schedule.extend(pairs)
        t.insert(1, t.pop())  # Drehen
    return [p for p in schedule if "BYE" not in p]


# 4. ---------------- TEAM‑STÄRKE ----------------

def calculate_team_strength(team_row: pd.Series, *, is_home: bool = False) -> float:
    players = team_row["Players"]
    if not players:
        return 50.0
    offense = sum(p["Offense"] for p in players) / len(players)
    defense = sum(p["Defense"] for p in players) / len(players)
    speed = sum(p["Speed"] for p in players) / len(players)
    chemistry = sum(p["Chemistry"] for p in players) / len(players)

    base = offense * 0.4 + defense * 0.3 + speed * 0.2 + chemistry * 0.1

    # Dynamische Modifikatoren
    form = random.uniform(-5, 5)           # Tagesform ±5 %
    momentum = team_row.get("Momentum", 0)  # Lauf
    home_adv = 3 if is_home else 0         # Heimbonus
    fan_support = random.uniform(-1, 2)    # Publikums‑Boost

    total = base
    for bonus in (form, momentum, home_adv, fan_support):
        total *= 1 + bonus / 100
    return total


# 5. ---------------- SPIEL‑SIMULATION ----------------

def simulate_match(df: pd.DataFrame, home_team: str, away_team: str, player_stats: pd.DataFrame) -> str:
    home_row = df.loc[df["Team"] == home_team].iloc[0]
    away_row = df.loc[df["Team"] == away_team].iloc[0]

    s_home = calculate_team_strength(home_row, is_home=True)
    s_away = calculate_team_strength(away_row)

    p_home = s_home / (s_home + s_away)
    g_home = max(0, int(random.gauss(p_home * 5, 1)))
    g_away = max(0, int(random.gauss((1 - p_home) * 5, 1)))

    # Tabelle aktualisieren
    df.loc[df["Team"] == home_team, ["Goals For", "Goals Against"]] += [g_home, g_away]
    df.loc[df["Team"] == away_team, ["Goals For", "Goals Against"]] += [g_away, g_home]

    if g_home > g_away:
        df.loc[df["Team"] == home_team, "Points"] += 3
    elif g_home < g_away:
        df.loc[df["Team"] == away_team, "Points"] += 3
    else:
        df.loc[df["Team"].isin([home_team, away_team]), "Points"] += 1

    # Spieler‑Stats
    for team_name, goals in ((home_team, g_home), (away_team, g_away)):
        roster = df.loc[df["Team"] == team_name, "Players"].iloc[0]
        weights = [max(1, p["Offense"] // 5) for p in roster]
        names = [p["Name"] for p in roster]
        for _ in range(goals):
            scorer = random.choices(names, weights)[0]
            assister = random.choice([n for n in names if n != scorer])
            player_stats.loc[player_stats["Player"] == scorer, "Goals"] += 1
            player_stats.loc[player_stats["Player"] == assister, "Assists"] += 1

    return f"{home_team} {g_home} : {g_away} {away_team}"


# 6. ---------------- PLAY‑OFFS ----------------

def simulate_playoff_round(pairings: list[tuple[str, str]], nord_df: pd.DataFrame, sued_df: pd.DataFrame) -> list[str]:
    winners: list[str] = []
    for a, b in pairings:
        df_a = nord_df if (nord_df["Team"] == a).any() else sued_df
        df_b = nord_df if (nord_df["Team"] == b).any() else sued_df
        row_a, row_b = df_a.loc[df_a["Team"] == a].iloc[0], df_b.loc[df_b["Team"] == b].iloc[0]
        s_a, s_b = calculate_team_strength(row_a), calculate_team_strength(row_b)
        p_a = s_a / (s_a + s_b)
        g_a = max(0, int(random.gauss(p_a * 5, 1)))
        g_b = max(0, int(random.gauss((1 - p_a) * 5, 1)))
        print(f"{a} {g_a} : {g_b} {b}")
        winners.append(a if g_a > g_b else b)
    return winners


def run_playoffs(nord_df: pd.DataFrame, sued_df: pd.DataFrame) -> str:
    nord_top = nord_df.sort_values(["Points", "Goals For"], ascending=False).head(4)["Team"].tolist()
    sued_top = sued_df.sort_values(["Points", "Goals For"], ascending=False).head(4)["Team"].tolist()

    pairings = [
        (nord_top[0], sued_top[3]),
        (nord_top[1], sued_top[2]),
        (nord_top[2], sued_top[1]),
        (nord_top[3], sued_top[0]),
    ]
    round_no = 1
    while len(pairings) > 1:
        print(f"\n=== PLAY‑OFF RUNDE {round_no} ===")
        winners = simulate_playoff_round(pairings, nord_df, sued_df)
        pairings = [(winners[i], winners[i + 1]) for i in range(0, len(winners), 2)]
        round_no += 1

    print("\n=== FINALE ===")
    champion = simulate_playoff_round(pairings, nord_df, sued_df)[0]
    print(f"\n🏆🏆🏆 Champion: {champion} 🏆🏆🏆\n")
    return champion


# 7. ---------------- INITIALISIERUNG ----------------

def initialise_game():
    if not nord_teams or not sued_teams:
        raise ValueError("Bitte füge Team‑Daten in nord_teams und sued_teams ein.")

    nord_df, sued_df = pd.DataFrame(nord_teams), pd.DataFrame(sued_teams)
    for df in (nord_df, sued_df):
        df["Points"], df["Goals For"], df["Goals Against"] = 0, 0, 0

    nord_schedule = create_round_robin_schedule(nord_teams)
    sued_schedule = create_round_robin_schedule(sued_teams)

    stats_rows = [
        {"Player": p["Name"], "Team": t["Team"], "Goals": 0, "Assists": 0, "Points": 0}
        for t in nord_teams + sued_teams for p in t["Players"]
    ]
    player_stats = pd.DataFrame(stats_rows)
    return nord_df, sued_df, nord_schedule, sued_schedule, player_stats, 1


# 8. ---------------- SAVE ODER NEU ----------------

def load_or_new(savefile: str):
    data = load_progress(savefile)
    if data:
        nord_df = pd.DataFrame(data["nord_df"])
        sued_df = pd.DataFrame(data["sued_df"])
        nord_schedule = data["nord_schedule"]
        sued_schedule = data["sued_schedule"]
        player_stats = pd.DataFrame(data["player_stats"])
        spieltag = data["spieltag"]
        return nord_df, sued_df, nord_schedule, sued_schedule, player_stats, spieltag
    return initialise_game()


# 9. ---------------- HAUPTSCHLEIFE ----------------

def main():
    savefile = "saves/savegame.json"
    nord_df, sued_df, nord_schedule, sued_schedule, player_stats, spieltag = load_or_new(savefile)
    print("Simulation gestartet – Strg‑C zum Beenden.\n")

    while True:
        if nord_schedule or sued_schedule:
            input(f"👉 Enter zum Simulieren von Spieltag {spieltag}…")
            print(f"\n=== Spieltag {spieltag} – Nord ===")
            for m in nord_schedule[: len(nord_df) // 2]:
                print(simulate_match(nord_df, m[0], m[1], player_stats))
            nord_schedule = nord_schedule[len(nord_df) // 2 :]

            print(f"\n=== Spieltag {spieltag} – Süd ===")
            for m in sued_schedule[: len(sued_df) // 2]:
                print(simulate_match(sued_df, m[0], m[1], player_stats))
            sued_schedule = sued_schedule[len(sued_df) // 2 :]

            # Tabellen
            print("\n=== Tabelle Nord ===")
            print(
                nord_df[["Team", "Points", "Goals For", "Goals Against"]]
                .sort_values(["Points", "Goals For"], ascending=False)
                .reset_index(drop=True)
            )
            print("\n=== Tabelle Süd ===")
            print(
                sued_df[["Team", "Points", "Goals For", "Goals Against"]]
                .sort_values(["Points", "Goals For"], ascending=False)
                .reset_index(drop=True)
            )

            # Top‑Scorer
            player_stats["Points"] = player_stats["Goals"] + player_stats["Assists"]
            print("\n=== Top 20 Scorer ===")
            print(player_stats.sort_values("Points", ascending=False).head(20).reset_index(drop=True))

            spieltag += 1
        else:
            # Play‑offs starten
            run_playoffs(nord_df, sued_df)
            break

        # Fortschritt sichern
        progress = {
            "nord_df": nord_df.to_dict("records"),
            "sued_df": sued_df.to_dict("records"),
            "nord_schedule": nord_schedule,
            "sued_schedule": sued_schedule,
            "player_stats": player_stats.to_dict("records"),
            "spieltag": spieltag,
        }
        save_progress(savefile, progress)
        print("💾 Speichert...")


if __name__ == "__main__":
    main()
