import os
import subprocess
import sys
from flask import Blueprint, request, jsonify
from core import state
from utils import process_image, encode_image_to_base64

images_bp = Blueprint('images', __name__)

@images_bp.route('/upload', methods=['POST'])
def upload_image():
    conversation = state.get_current_conversation()

    data = request.json
    image_data = data.get('image')

    if not image_data:
        return jsonify({'error': '没有图片'}), 400

    try:
        image_path = process_image(image_data)
        if not image_path:
            return jsonify({'error': '图片处理失败'}), 500

        image_base64 = encode_image_to_base64(image_path)
        if not image_base64:
            return jsonify({'error': '图片编码失败'}), 500

        image_info = {
            'name': f'image_{len(conversation.images) + 1}',
            'data': image_base64
        }
        conversation.images.append(image_info)

        try:
            os.unlink(image_path)
        except:
            pass

        return jsonify({
            'success': True,
            'message': '图片上传成功',
            'images': conversation.images
        })
    except Exception as e:
        try:
            if 'image_path' in locals():
                os.unlink(image_path)
        except:
            pass
        return jsonify({'error': f'图片上传失败：{str(e)}'}), 500


@images_bp.route('/remove', methods=['DELETE'])
def remove_image():
    conversation = state.get_current_conversation()
    conversation.images = []
    return jsonify({'success': True, 'message': '图片已移除'})


@images_bp.route('/remove/<int:index>', methods=['DELETE'])
def remove_single_image(index):
    conversation = state.get_current_conversation()
    if 0 <= index < len(conversation.images):
        conversation.images.pop(index)
        return jsonify({'success': True, 'message': '图片已移除', 'images': conversation.images})
    return jsonify({'error': '无效的图片索引'}), 400


@images_bp.route('/screenshot', methods=['POST'])
def screenshot():
    conversation = state.get_current_conversation()

    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'utils', 'screenshot.py')

        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return jsonify({'error': f'截图失败：{result.stderr}'}), 500

        output = result.stdout.strip()

        if output == "CANCELLED":
            return jsonify({'error': '截图已取消'}), 400

        image_data = output

        try:
            image_path = process_image(f"data:image/png;base64,{image_data}")
        except:
            image_path = None

        if not image_path:
            image_info = {
                'name': f'image_{len(conversation.images) + 1}',
                'data': image_data
            }
            conversation.images.append(image_info)

            return jsonify({
                'success': True,
                'message': '截图成功',
                'images': conversation.images
            })

        image_base64 = encode_image_to_base64(image_path)
        if not image_base64:
            return jsonify({'error': '图片编码失败'}), 500

        image_info = {
            'name': f'image_{len(conversation.images) + 1}',
            'data': image_base64
        }
        conversation.images.append(image_info)

        try:
            os.unlink(image_path)
        except:
            pass

        return jsonify({
            'success': True,
            'message': '截图成功',
            'images': conversation.images
        })

    except subprocess.TimeoutExpired:
        return jsonify({'error': '截图超时，请重试'}), 500
    except Exception as e:
        return jsonify({'error': f'截图失败：{str(e)}'}), 500
