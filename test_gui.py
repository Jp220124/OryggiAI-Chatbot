import tkinter as tk
import sys
print("Starting tkinter test...")
sys.stdout.flush()

root = tk.Tk()
root.title("Test Window")
root.geometry("400x300")
root.lift()
root.attributes('-topmost', True)
root.focus_force()

tk.Label(root, text="Tkinter Works!", font=("Arial", 24)).pack(pady=50)
tk.Button(root, text="Close", command=root.destroy).pack()

print("Window created, starting mainloop...")
sys.stdout.flush()
root.mainloop()
print("Mainloop ended")
