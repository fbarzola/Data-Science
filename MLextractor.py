#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from datetime import date
import re
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.colors as mcolors
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib.pyplot as plt
import seaborn as sns
import webbrowser
import os
import warnings
warnings.filterwarnings("ignore")

class App:
    def __init__(self, master):
        self.master = master
        self.master.title("Ingreso de URL")
        
        self.style = ttk.Style()
        self.style.theme_use('clam')

        self.window_width = 400
        self.window_height = 200
        self.screen_width = self.master.winfo_screenwidth()
        self.screen_height = self.master.winfo_screenheight()
        self.position_top = int(self.screen_height / 2 - self.window_height / 2)
        self.position_right = int(self.screen_width / 2 - self.window_width / 2)
        self.master.geometry(f'{self.window_width}x{self.window_height}+{self.position_right}+{self.position_top}')
        
        self.master.attributes('-topmost', 1)

        self.url_input = tk.StringVar() 

        ttk.Label(self.master, text="Por favor, ingrese la URL que desea analizar:").pack(pady=20)
        self.url_entry = ttk.Entry(self.master, width=50, textvariable=self.url_input)
        self.url_entry.pack(pady=10)

        ttk.Button(self.master, text="Comenzar", command=self.on_submit).pack(pady=20)

    def on_submit(self):
        url = self.url_entry.get()
        self.master.withdraw() 
        self.extraer_datos(url)

    def extraer_datos(self, url):
        
        search_term_match = re.search(r'https://listado\.mercadolibre\.com\.ar/(.*?)#D', url)
        if search_term_match:
            search_term = search_term_match.group(1).replace('-', ' ').lower()
            search_terms = search_term.split()
        else:
            print("No se pudo extraer el término de búsqueda de la URL.")
            return None

        print(f"Término de búsqueda extraído: {search_term}")  

        search_number_match = re.search(r'\d+', search_term)
        search_number = search_number_match.group() if search_number_match else None

        titulos = []
        urls = []
        precios = []
        cuotas = []

        pagina = 1  

        while url:
            print(f"Procesando página {pagina}...")  
            response = requests.get(url)
            if response.status_code != 200:
                print("Error al obtener la página. Código de estado:", response.status_code)
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')

            items = soup.find_all('div', class_='ui-search-result__content-wrapper')
            if not items:
                print(f"No se encontraron items en la página {pagina}.")
                break

            for item in items:
                estado = item.find('span', class_='ui-search-item__group__element ui-search-item__details')
                if estado and 'Usado' in estado.text:
                    continue
                titulo = item.find('h2', class_='ui-search-item__title')
                if titulo:
                    titulo_texto = titulo.text.lower()
                    matching_terms = [term for term in search_terms if term in titulo_texto]

                    if search_number and search_number in titulo_texto and len(matching_terms) >= 2:
                        titulos.append(titulo.text if titulo else 'Sin título')
                        item_url = item.find('a', class_='ui-search-item__group__element ui-search-link__title-card ui-search-link')
                        urls.append(item_url['href'] if item_url else 'Sin URL')
                        precio = item.find('span', class_='andes-money-amount ui-search-price__part ui-search-price__part--medium andes-money-amount--cents-superscript')
                        precios.append(precio.text if precio else 'Sin precio')
                        cuota_info = item.find('div', class_='ui-search-item__group__element ui-search-installments ui-search-color--LIGHT_GREEN')
                        cuotas.append(cuota_info.text.strip() if cuota_info else 'Sin cuotas')

            next_button = soup.find('li', class_='andes-pagination__button andes-pagination__button--next')
            if next_button:
                next_link = next_button.find('a')
                if next_link:
                    url = next_link['href']
                    print(f"Encontrado enlace a la siguiente página: {url}")  
                    pagina += 1 
                else:
                    print("No se encontró el enlace dentro del botón de 'Siguiente'.")  
                    url = None
            else:
                print("Finalización de búsqueda.")  
                url = None

        df = pd.DataFrame({'Publicaciones': titulos, 'URL': urls, 'Precio': precios, 'Cuotas': cuotas})
        df['Fecha'] = date.today()
        
        df['Precio_numerico'] = df['Precio'].apply(self.limpiar_precio)

        self.mostrar_frame_progreso(df)


    def limpiar_precio(self, precio):
        if not precio:
            return np.nan
        if 'US$' in precio:
            precio_limpio = re.sub(r'[^0-9,]', '', precio.replace('US$', ''))
            precio_limpio = precio_limpio.replace(',', '')
            try:
                return float(precio_limpio) * 1300
            except ValueError:
                return np.nan
        else:
            precio_limpio = re.sub(r'[^0-9,]', '', precio)
            precio_limpio = precio_limpio.replace(',', '')
            try:
                return float(precio_limpio)
            except ValueError:
                return np.nan

    def mostrar_frame_progreso(self, df):
        self.progress_window = tk.Toplevel(self.master)
        self.progress_window.title("Proceso de Extracción")
        self.progress_window.geometry('400x200')
        
        frame_progreso = tk.Frame(self.progress_window, width=300, height=150)
        frame_progreso.pack(pady=20)
        lbl_cargando = tk.Label(frame_progreso, text="Extrayendo información...", font=("Arial", 12))
        lbl_cargando.pack(pady=10)
        progress_bar = ttk.Progressbar(frame_progreso, orient=tk.HORIZONTAL, length=300, mode='determinate')
        progress_bar.pack(pady=10)
        progress_bar['maximum'] = 100
        
        boton_finalizar = tk.Button(frame_progreso, text="Finalizar", state='disabled', command=lambda: self.cerrar_progreso(df))
        boton_finalizar.pack(pady=10)

        def realizar_extraccion():
            max_value = len(df['URL'])
            progress_bar['maximum'] = max_value

            stocks = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(self.extraer_stock_disponible, url): url for url in df['URL']}
                for future in as_completed(futures):
                    result = future.result()
                    stocks.append(result)
                    progress_bar['value'] += 1
                    progress_bar.update_idletasks()

            df['Stock Disponible'] = stocks
            df['Stock Disponible'] = df['Stock Disponible'].apply(lambda x: 'Última Disponible' if x == 0 else x)

            self.master.after(0, lambda: self.habilitar_boton_finalizar(boton_finalizar))

        threading.Thread(target=realizar_extraccion).start()
        
    def cerrar_progreso(self, df_sorted_visible):
        self.guardar_csv(df_sorted_visible)
        self.progress_window.destroy()
        self.mostrar_resultados(df_sorted_visible)

    def habilitar_boton_finalizar(self, boton_finalizar):
        boton_finalizar.config(state='normal')

    def extraer_stock_disponible(self, url):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                stock_info = soup.find('span', class_='ui-pdp-buybox__quantity__available')
                if stock_info:
                    stock_text = stock_info.get_text()
                    stock_number = re.search(r'\d+', stock_text)
                    if stock_number:
                        return int(stock_number.group())
        except requests.RequestException as e:
            print(f"Error al acceder a {url}: {e}")
        return 0

    def mostrar_resultados(self, df):
        df_sorted = df.copy()
        df_sorted = df_sorted.sort_values(by='Precio_numerico', ascending=True)

        self.df_original = df_sorted.copy()

        column_order = ['Publicaciones', 'URL', 'Precio', 'Cuotas', 'Stock Disponible', 'Fecha', 'Precio_numerico']
        df_sorted = df_sorted[column_order]

        df_sorted_visible = df_sorted.drop(columns=['Precio_numerico'])

        self.mostrar_dataframe(df_sorted_visible)

    def graficar_precios(self):
        df = self.df_original.copy()
        df['Precio_numerico'] = df['Precio'].apply(self.limpiar_precio)

        # Definir marcas que se graficarán en rojo
        marcas_rojas = ['enova', 'skyworth', 'konka', 'quantum']

        # Asignar colores basados en las marcas especificadas
        df['Color'] = df['Publicaciones'].apply(lambda x: 'red' if any(marca in x.lower() for marca in marcas_rojas) else 'blue')

        # Crear la figura y los ejes
        fig, ax = plt.subplots(figsize=(13, 9))

        # Graficar puntos scatter para cada color
        for color in ['red', 'blue']:
            data = df[df['Color'] == color]
            ax.scatter(data.index, data['Precio_numerico'], label='Marcas destacadas' if color == 'red' else 'Otras marcas', c=color)

        # Dibujar líneas horizontales en los precios mínimos de las marcas rojas
        for marca in marcas_rojas:
            data_marca = df[df['Publicaciones'].str.lower().str.contains(marca)]
            if not data_marca.empty:
                precio_minimo = data_marca['Precio_numerico'].min()
                ax.axhline(y=precio_minimo, color='red', linestyle='--', label=f'Precio mínimo de {marca.capitalize()}')

        # Etiquetas para puntos rojos (Enova, Skyworth, Konka, Quantum)
        for marca in marcas_rojas:
            data_marca = df[df['Publicaciones'].str.lower().str.contains(marca)]
            for idx, row in data_marca.iterrows():
                ax.annotate(marca.capitalize(), (idx, row['Precio_numerico']), textcoords="offset points", xytext=(0, 10), ha='center', fontsize=8, color='red')

        ax.set_title('Precios de Productos')
        ax.set_xlabel('Productos')
        ax.set_ylabel('Precio (ARS)')
        ax.legend(title='Marcas')
        plt.xticks(rotation=45)
        plt.tight_layout()

        # Mostrar la gráfica en una ventana de Tkinter
        grafica_window = tk.Toplevel(self.master)
        grafica_window.title("Gráfico de Precios")

        canvas = FigureCanvasTkAgg(fig, master=grafica_window)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)




    def mostrar_dataframe(self, df_sorted_visible):
        self.resultados_window = tk.Toplevel(self.master)
        self.resultados_window.title("Listado de Productos Ordenados por precio")

        screen_width = self.resultados_window.winfo_screenwidth()
        screen_height = self.resultados_window.winfo_screenheight()
        window_width = 1200 
        window_height = screen_height // 2  
        self.resultados_window.geometry(f'{window_width}x{window_height}')

        frame = tk.Frame(self.resultados_window)
        frame.pack(fill='both', expand=True)

        treeview = ttk.Treeview(frame, columns=list(df_sorted_visible.columns), show='headings')

        for column in df_sorted_visible.columns:
            treeview.heading(column, text=column)
            treeview.column(column, anchor='center')

        for index, row in df_sorted_visible.iterrows():
            tags = []
            if 'Enova' in row['Publicaciones']: 
                tags.append('enova')
            if 'Skyworth' in row['Publicaciones']:
                tags.append('Skyworth')
            if 'Konka' in row['Publicaciones']:
                tags.append('Konka')
            if 'Quantum' in row['Publicaciones']:
                tags.append('Quantum')

            if tags:
                treeview.insert("", "end", values=list(row), tags=tags)
            else:
                treeview.insert("", "end", values=list(row))

        treeview.tag_configure('enova', background='lightgreen')
        treeview.tag_configure('Skyworth', background='lightgreen')
        treeview.tag_configure('Konka', background='lightgreen')
        treeview.tag_configure('Quantum', background='lightgreen')

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=treeview.yview, style="Vertical.TScrollbar")
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Vertical.TScrollbar", troughcolor="gray", gripcount=0, borderwidth=0)
        scrollbar.pack(side="right", fill="y")

        treeview.configure(yscrollcommand=scrollbar.set)

        treeview.pack(fill='both', expand=True)
        treeview.bind("<Button-1>", self.on_click)

        button_frame = tk.Frame(self.resultados_window)
        button_frame.pack(pady=10)

        button_cerrar = tk.Button(button_frame, text="Cerrar", command=self.resultados_window.destroy, width=10)
        button_cerrar.pack(side=tk.LEFT, padx=5)

        button_graficar = tk.Button(button_frame, text="Graficar precios", command=self.graficar_precios, width=15)
        button_graficar.pack(side=tk.LEFT, padx=5)


    def on_click(self, event):
        treeview = event.widget
        item = treeview.identify_row(event.y)
        column = treeview.identify_column(event.x)
        column_index = int(column.replace('#', '')) - 1 

        if item:
            if column_index == 1:
                url = treeview.item(item)['values'][column_index]
                if url and url != 'Sin URL':
                    webbrowser.open(url)

    def obtener_nombre_archivo_consecutivo(self, base_name, extension):
        files = os.listdir('.')
        
        pattern = re.compile(rf'{re.escape(base_name)}(\d*)\.{re.escape(extension)}')
        matching_files = [f for f in files if pattern.match(f)]
        
        numbers = []
        for file in matching_files:
            match = pattern.match(file)
            if match.group(1):
                numbers.append(int(match.group(1)))
            else:
                numbers.append(0)
        
        if numbers:
            next_number = max(numbers) + 1
        else:
            next_number = 1
        
        new_filename = f"{base_name}{next_number}.{extension}"
        return new_filename
    
    def guardar_csv(self, df_sorted_visible):
        base_name = 'productos_ordenados'
        extension = 'csv'
        df_sorted_visible = df_sorted_visible.sort_values(by='Precio_numerico') 
        csv_filename = self.obtener_nombre_archivo_consecutivo(base_name, extension)
        df_sorted_visible.to_csv(csv_filename, index=False)
        print(f"DataFrame guardado en {csv_filename}")
        os.startfile(csv_filename)


def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()

