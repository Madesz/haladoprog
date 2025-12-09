import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import random
import sqlite3
import os
from datetime import datetime

class ImageAnnotationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Képannotációs Rendszer")
        self.root.geometry("1000x600")
        
        self.image = None
        self.image_tk = None
        self.annotations = []
        self.labels = []
        self.current_label = ""
        self.draw_mode = "polygon"
        self.points = []
        self.current_color = "#FF6B6B"
        self.current_image_path = ""
        
        # Adatbázis inicializálása
        self.init_database()
        
        self.setup_ui()
        
    def init_database(self):
        """SQLite adatbázis inicializálása"""
        self.db_path = "annotations.db"
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # Cimkék tábla
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS labels (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                color TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Annotációk tábla
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS annotations (
                id INTEGER PRIMARY KEY,
                image_path TEXT,
                label_id INTEGER,
                annotation_type TEXT,
                coordinates TEXT,
                color TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (label_id) REFERENCES labels(id)
            )
        ''')
        
        self.conn.commit()
        self.load_labels_from_db()
        
    def load_labels_from_db(self):
        """Cimkék betöltése az adatbázisból"""
        self.cursor.execute('SELECT id, name, color FROM labels')
        db_labels = self.cursor.fetchall()
        
        if db_labels:
            self.labels = [{"id": row[0], "name": row[1], "color": row[2], "count": 0} for row in db_labels]
        else:
            # Alapértelmezett cimkék hozzáadása
            default_labels = ["kutya", "macska", "madár", "autó"]
            colors = ["#FF6B6B", "#4ECDC4", "#FFE66D", "#95E1D3"]
            for label, color in zip(default_labels, colors):
                self.cursor.execute('INSERT INTO labels (name, color) VALUES (?, ?)', (label, color))
            self.conn.commit()
            self.load_labels_from_db()
        
    def setup_ui(self):
        # Főpanel
        main = tk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Bal oldal - Canvas
        left = tk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        tk.Label(left, text="Kép Feltöltése és Rajzolás", font=("Arial", 12, "bold")).pack()
        
        btn_frame = tk.Frame(left)
        btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(btn_frame, text="Kép", command=self.load_image, bg="#3498db", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Törlés", command=self.clear_canvas, bg="#e74c3c", fg="white").pack(side=tk.LEFT, padx=2)
        
        mode_frame = tk.Frame(left)
        mode_frame.pack(fill=tk.X, pady=5)
        tk.Button(mode_frame, text="Sokszög", command=lambda: self.set_draw_mode("polygon"), bg="#27ae60", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(mode_frame, text="Téglalap", command=lambda: self.set_draw_mode("box"), bg="#27ae60", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(mode_frame, text="Vissza", command=self.undo, bg="#e67e22", fg="white").pack(side=tk.LEFT, padx=2)
        
        self.canvas = tk.Canvas(left, width=450, height=450, bg="white", cursor="crosshair", relief=tk.SUNKEN, borderwidth=2)
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=5)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        
        self.root.bind("<Return>", lambda e: self.finish_polygon())
        self.root.bind("<Escape>", lambda e: self.clear_canvas())
        
        # Jobb oldal - Cimkék
        right = tk.Frame(main, width=300)
        right.pack(side=tk.LEFT, fill=tk.BOTH, padx=(5, 0))
        right.pack_propagate(False)
        
        tk.Label(right, text="Cimkék Kezelése", font=("Arial", 12, "bold")).pack()
        
        label_frame = tk.Frame(right)
        label_frame.pack(fill=tk.X, pady=5)
        self.label_input = tk.Entry(label_frame, width=15)
        self.label_input.pack(side=tk.LEFT, padx=2)
        tk.Button(label_frame, text="Hozzáadás", command=self.add_label, bg="#27ae60", fg="white").pack(side=tk.LEFT, padx=2)
        
        tk.Label(right, text="Elérhető cimkék:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10, 2))
        
        scrollbar = tk.Scrollbar(right)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.labels_listbox = tk.Listbox(right, font=("Arial", 9), yscrollcommand=scrollbar.set, height=10)
        self.labels_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.labels_listbox.bind("<<ListboxSelect>>", self.on_label_select)
        scrollbar.config(command=self.labels_listbox.yview)
        
        color_frame = tk.Frame(right)
        color_frame.pack(fill=tk.X, pady=5)
        tk.Label(color_frame, text="Szín:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=2)
        self.color_button = tk.Button(color_frame, width=15, height=2, bg="#FF6B6B", command=self.choose_color, relief=tk.SUNKEN, borderwidth=2)
        self.color_button.pack(side=tk.LEFT, padx=2)
        
        tk.Button(right, text="Cimke Törlés", command=self.delete_label, bg="#e74c3c", fg="white", width=30).pack(fill=tk.X, pady=5)
        
        stats_frame = tk.LabelFrame(right, text="Statisztika", font=("Arial", 9, "bold"), padx=5, pady=5)
        stats_frame.pack(fill=tk.X, pady=5)
        self.stats_label = tk.Label(stats_frame, text="Annotációk: 0\nAktív cimke: --", font=("Arial", 9), justify=tk.LEFT)
        self.stats_label.pack(anchor=tk.W)
        
        # Adatbázis info
        db_frame = tk.LabelFrame(right, text="Adatbázis", font=("Arial", 8, "bold"), padx=5, pady=5, bg="#e8f4f8")
        db_frame.pack(fill=tk.X, pady=5)
        self.db_label = tk.Label(db_frame, text="Össz. Annotáció DB-ben: 0\nFájl: annotations.db", font=("Arial", 8), justify=tk.LEFT, bg="#e8f4f8")
        self.db_label.pack(anchor=tk.W)
        
        tk.Button(right, text="DB Statisztika", command=self.show_db_stats, bg="#9b59b6", fg="white", width=30).pack(fill=tk.X, pady=3)
        
        self.update_labels_list()
        self.update_db_stats()
        
    def set_draw_mode(self, mode):
        self.draw_mode = mode
        self.points = []
        
    def on_canvas_click(self, event):
        if not self.image or not self.current_label:
            messagebox.showwarning("Figyelem", "Válassz képet és cimkét!")
            return
        if self.draw_mode == "polygon":
            self.points.append((event.x, event.y))
            self.redraw_canvas()
        elif self.draw_mode == "box":
            self.points = [(event.x, event.y)]
    
    def on_canvas_drag(self, event):
        if self.draw_mode == "box" and self.points:
            self.redraw_canvas()
            x0, y0 = self.points[0]
            self.canvas.create_rectangle(x0, y0, event.x, event.y, outline=self.current_color, width=2)
    
    def on_canvas_release(self, event):
        if self.draw_mode == "box" and len(self.points) == 1 and self.current_label:
            x0, y0 = self.points[0]
            self.annotations.append({
                "type": "box", "label": self.current_label, "color": self.current_color,
                "x0": min(x0, event.x), "y0": min(y0, event.y), "x1": max(x0, event.x), "y1": max(y0, event.y)
            })
            self.points = []
            self.update_label_count()
            self.redraw_canvas()
    
    def finish_polygon(self):
        if self.draw_mode == "polygon" and len(self.points) >= 3 and self.current_label:
            self.annotations.append({"type": "polygon", "label": self.current_label, "color": self.current_color, "points": self.points.copy()})
            self.points = []
            self.update_label_count()
            self.redraw_canvas()
        else:
            messagebox.showwarning("Hiba", "Min. 3 pont szükséges!")
    
    def undo(self):
        if self.points:
            self.points.pop()
        elif self.annotations:
            self.annotations.pop()
            self.update_label_count()
        self.redraw_canvas()
    
    def redraw_canvas(self):
        if not self.image:
            return
        self.image_tk = ImageTk.PhotoImage(self.image)
        self.canvas.create_image(0, 0, image=self.image_tk, anchor=tk.NW)
        
        for ann in self.annotations:
            if ann["type"] == "polygon":
                points = ann["points"]
                flat_points = [coord for point in points for coord in point]
                self.canvas.create_polygon(*flat_points, fill=ann["color"]+"33", outline=ann["color"], width=2)
                self.canvas.create_text(points[0][0]+5, points[0][1]-5, text=ann["label"], fill=ann["color"], font=("Arial", 9, "bold"), anchor=tk.NW)
            elif ann["type"] == "box":
                self.canvas.create_rectangle(ann["x0"], ann["y0"], ann["x1"], ann["y1"], fill=ann["color"]+"33", outline=ann["color"], width=2)
                self.canvas.create_text(ann["x0"]+5, ann["y0"]-5, text=ann["label"], fill=ann["color"], font=("Arial", 9, "bold"), anchor=tk.NW)
        
        if self.draw_mode == "polygon":
            for point in self.points:
                self.canvas.create_oval(point[0]-4, point[1]-4, point[0]+4, point[1]+4, fill=self.current_color, outline="black")
            if len(self.points) > 1:
                for i in range(len(self.points)-1):
                    self.canvas.create_line(self.points[i][0], self.points[i][1], self.points[i+1][0], self.points[i+1][1], fill=self.current_color, width=2)
    
    def load_image(self):
        filename = filedialog.askopenfilename(title="Válassz képet", filetypes=[("Képfájlok", "*.jpg *.jpeg *.png *.bmp *.gif"), ("Összes", "*.*")])
        if filename:
            try:
                img = Image.open(filename)
                img.thumbnail((450, 450), Image.Resampling.LANCZOS)
                self.image = img
                self.current_image_path = filename
                self.annotations = []
                self.points = []
                self.update_label_count()
                self.redraw_canvas()
                messagebox.showinfo("Siker", "Kép betöltve!")
            except Exception as e:
                messagebox.showerror("Hiba", f"Nem lehet betölteni: {e}")
    
    def clear_canvas(self):
        self.canvas.delete("all")
        self.annotations = []
        self.points = []
        self.image = None
        self.current_label = ""
        self.current_image_path = ""
        self.update_label_count()
    
    def add_label(self):
        label_text = self.label_input.get().strip()
        if not label_text:
            messagebox.showwarning("Hiba", "A cimke üres!")
            return
        if any(l["name"] == label_text for l in self.labels):
            messagebox.showwarning("Hiba", "Ez már létezik!")
            return
        
        colors = ["#FF6B6B", "#4ECDC4", "#FFE66D", "#95E1D3", "#F7B731", "#A29BFE", "#FD79A8", "#6C5CE7", "#00B894"]
        color = random.choice(colors)
        
        # Adatbázisba mentés
        self.cursor.execute('INSERT INTO labels (name, color) VALUES (?, ?)', (label_text, color))
        self.conn.commit()
        
        self.label_input.delete(0, tk.END)
        self.load_labels_from_db()
        self.update_labels_list()
    
    def delete_label(self):
        selection = self.labels_listbox.curselection()
        if selection:
            idx = selection[0]
            label = self.labels[idx]
            
            # Adatbázisból törlés
            self.cursor.execute('DELETE FROM labels WHERE id = ?', (label["id"],))
            self.cursor.execute('DELETE FROM annotations WHERE label_id = ?', (label["id"],))
            self.conn.commit()
            
            self.annotations = [a for a in self.annotations if a["label"] != label["name"]]
            self.load_labels_from_db()
            self.update_labels_list()
            self.update_label_count()
            self.redraw_canvas()
            self.update_db_stats()
    
    def on_label_select(self, event):
        selection = self.labels_listbox.curselection()
        if selection:
            idx = selection[0]
            label = self.labels[idx]
            self.current_label = label["name"]
            self.current_color = label["color"]
            self.color_button.config(bg=label["color"])
            self.update_stats()
    
    def choose_color(self):
        from tkinter.colorchooser import askcolor
        color = askcolor(color=self.current_color, title="Válassz színt")
        if color[1]:
            self.current_color = color[1]
            self.color_button.config(bg=self.current_color)
            
            # Adatbázis frissítés
            for label in self.labels:
                if label["name"] == self.current_label:
                    self.cursor.execute('UPDATE labels SET color = ? WHERE id = ?', (self.current_color, label["id"]))
                    self.conn.commit()
                    label["color"] = self.current_color
                    break
            
            self.update_labels_list()
            self.redraw_canvas()
    
    def update_labels_list(self):
        self.labels_listbox.delete(0, tk.END)
        for label in self.labels:
            self.labels_listbox.insert(tk.END, f"● {label['name']} ({label['count']})")
    
    def update_label_count(self):
        for label in self.labels:
            label["count"] = sum(1 for ann in self.annotations if ann["label"] == label["name"])
        self.update_labels_list()
        self.update_stats()
    
    def update_stats(self):
        total = len(self.annotations)
        active = self.current_label if self.current_label else "--"
        self.stats_label.config(text=f"Annotációk: {total}\nAktív cimke: {active}")
    
    def update_db_stats(self):
        """Adatbázis statisztika frissítése"""
        self.cursor.execute('SELECT COUNT(*) FROM annotations')
        total_annotations = self.cursor.fetchone()[0]
        self.db_label.config(text=f"Össz. Annotáció DB-ben: {total_annotations}\nFájl: annotations.db")
    
    def save_annotations_to_db(self):
        """Annotációk mentése az adatbázisba"""
        if not self.current_image_path or not self.annotations:
            messagebox.showwarning("Figyelem", "Nincs kép vagy annotáció!")
            return
        
        for ann in self.annotations:
            label_id = None
            for label in self.labels:
                if label["name"] == ann["label"]:
                    label_id = label["id"]
                    break
            
            if label_id:
                # Koordináták JSON formátumban
                if ann["type"] == "polygon":
                    coords = str(ann["points"])
                else:
                    coords = f"{ann['x0']},{ann['y0']},{ann['x1']},{ann['y1']}"
                
                self.cursor.execute('''
                    INSERT INTO annotations (image_path, label_id, annotation_type, coordinates, color)
                    VALUES (?, ?, ?, ?, ?)
                ''', (self.current_image_path, label_id, ann["type"], coords, ann["color"]))
        
        self.conn.commit()
        self.update_db_stats()
        messagebox.showinfo("Siker", f"{len(self.annotations)} annotáció mentve az adatbázisba!")
    
    def show_db_stats(self):
        """Adatbázis statisztika megjelenítése"""
        self.cursor.execute('SELECT name, COUNT(*) FROM annotations a JOIN labels l ON a.label_id = l.id GROUP BY l.name')
        results = self.cursor.fetchall()
        
        stats_text = "Adatbázis Statisztika:\n\n"
        total = 0
        for label_name, count in results:
            stats_text += f"{label_name}: {count}\n"
            total += count
        stats_text += f"\n─────────────────\nÖsszes: {total}"
        
        messagebox.showinfo("Adatbázis Statisztika", stats_text)


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageAnnotationApp(root)
    
    # Mentés az alkalmazás bezárásakor
    def on_closing():
        if app.annotations:
            if messagebox.askyesno("Mentés", "Menti az annotációkat az adatbázisba?"):
                app.save_annotations_to_db()
        app.conn.close()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()