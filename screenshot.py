import mss
import mss.tools
import tkinter as tk
from PIL import Image, ImageTk
import base64
import io


class ScreenshotSelector:
    def __init__(self):
        self.result = None
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.tk_img = None
        self.canvas_img = None
        
    def select_region(self):
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            sct_img = sct.grab(monitor)
            
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        
        self.root = tk.Tk()
        self.root.title("请框选截图区域")
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-alpha', 0.3)
        self.root.update()
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f"{screen_width}x{screen_height}")
        
        self.canvas = tk.Canvas(self.root, cursor="cross")
        self.canvas.pack(fill="both", expand=True)
        
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas_img = self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")
        
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.root.bind("<Escape>", self.cancel)
        self.canvas.bind("<Escape>", self.cancel)
        
        self.root.mainloop()
        
        self.root.destroy()
        
        return self.result
    
    def on_button_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="red", width=2
        )
    
    def on_move_press(self, event):
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)
    
    def on_button_release(self, event):
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        if x2 - x1 < 10 or y2 - y1 < 10:
            self.result = None
        else:
            with mss.mss() as sct:
                monitor = sct.monitors[0]
                sct_img = sct.grab(monitor)
            
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            cropped = img.crop((x1, y1, x2, y2))
            
            buffer = io.BytesIO()
            cropped.save(buffer, format='PNG')
            buffer.seek(0)
            
            self.result = {
                'data': base64.b64encode(buffer.read()).decode('utf-8'),
                'width': x2 - x1,
                'height': y2 - y1
            }
        
        self.root.quit()
    
    def cancel(self, event):
        self.result = None
        self.root.quit()


def take_screenshot():
    selector = ScreenshotSelector()
    return selector.select_region()


if __name__ == "__main__":
    result = take_screenshot()
    if result:
        print(result['data'])
    else:
        print("CANCELLED")
