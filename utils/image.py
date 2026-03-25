import base64
import io
import os
import tempfile
import uuid
from PIL import Image


def process_image(image_data):
    try:
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        max_size = (512, 512)
        image.thumbnail(max_size, Image.LANCZOS)
        
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"temp_{uuid.uuid4()}.jpg")
        image.save(temp_path, 'JPEG', quality=70)
        
        return temp_path
    except Exception as e:
        print(f"图像处理失败: {str(e)}")
        return None


def encode_image_to_base64(image_path):
    try:
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print(f"图像编码失败: {str(e)}")
        return None
