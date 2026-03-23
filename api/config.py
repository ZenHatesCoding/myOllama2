from flask import Blueprint, request, jsonify
from extensions import state
from config_manager import load_config, save_config

config_bp = Blueprint('config', __name__)

@config_bp.route('/config', methods=['GET'])
def get_config():
    config = load_config()
    return jsonify({
        'llm_provider': state.llm_provider,
        'ollama_base_url': state.ollama_base_url,
        'openai_endpoints': state.openai_endpoints,
        'openai_current_endpoint': state.openai_current_endpoint,
        'openai_current_model': state.openai_current_model,
        'anthropic_endpoints': state.anthropic_endpoints,
        'anthropic_current_endpoint': state.anthropic_current_endpoint,
        'anthropic_current_model': state.anthropic_current_model,
        'max_context_turns': state.max_context_turns,
        'speech_recognition_lang': state.speech_recognition_lang,
        'speech_synthesis_lang': state.speech_synthesis_lang,
        'max_recording_time': state.max_recording_time
    })


@config_bp.route('/config', methods=['PUT'])
def update_config():
    data = request.json

    llm_provider = data.get('llm_provider')
    ollama_base_url = data.get('ollama_base_url')
    openai_endpoints = data.get('openai_endpoints')
    openai_current_endpoint = data.get('openai_current_endpoint')
    openai_current_model = data.get('openai_current_model')
    anthropic_endpoints = data.get('anthropic_endpoints')
    anthropic_current_endpoint = data.get('anthropic_current_endpoint')
    anthropic_current_model = data.get('anthropic_current_model')
    max_turns = data.get('max_context_turns')
    speech_recognition_lang = data.get('speech_recognition_lang')
    speech_synthesis_lang = data.get('speech_synthesis_lang')
    max_recording_time = data.get('max_recording_time')

    if llm_provider:
        state.llm_provider = llm_provider

    if ollama_base_url:
        state.ollama_base_url = ollama_base_url

    if openai_endpoints is not None:
        state.openai_endpoints = openai_endpoints
    if openai_current_endpoint is not None:
        state.openai_current_endpoint = openai_current_endpoint
    if openai_current_model is not None:
        state.openai_current_model = openai_current_model

    if anthropic_endpoints is not None:
        state.anthropic_endpoints = anthropic_endpoints
    if anthropic_current_endpoint is not None:
        state.anthropic_current_endpoint = anthropic_current_endpoint
    if anthropic_current_model is not None:
        state.anthropic_current_model = anthropic_current_model

    if max_turns is not None and isinstance(max_turns, int) and max_turns > 0:
        state.max_context_turns = max_turns

    if speech_recognition_lang:
        state.speech_recognition_lang = speech_recognition_lang

    if speech_synthesis_lang:
        state.speech_synthesis_lang = speech_synthesis_lang

    if max_recording_time is not None and isinstance(max_recording_time, int) and 5 <= max_recording_time <= 120:
        state.max_recording_time = max_recording_time

    config = load_config()
    config['llm_provider'] = state.llm_provider
    config['ollama_base_url'] = state.ollama_base_url
    config['openai_endpoints'] = state.openai_endpoints
    config['openai_current_endpoint'] = state.openai_current_endpoint
    config['openai_current_model'] = state.openai_current_model
    config['anthropic_endpoints'] = state.anthropic_endpoints
    config['anthropic_current_endpoint'] = state.anthropic_current_endpoint
    config['anthropic_current_model'] = state.anthropic_current_model
    config['max_context_turns'] = state.max_context_turns
    config['speech_recognition_lang'] = state.speech_recognition_lang
    config['speech_synthesis_lang'] = state.speech_synthesis_lang
    config['max_recording_time'] = state.max_recording_time
    save_config(config)

    return jsonify({
        'success': True,
        'max_context_turns': state.max_context_turns,
        'speech_recognition_lang': state.speech_recognition_lang,
        'speech_synthesis_lang': state.speech_synthesis_lang,
        'max_recording_time': state.max_recording_time
    })


@config_bp.route('/openai/endpoints', methods=['GET'])
def get_openai_endpoints():
    return jsonify({
        'endpoints': state.openai_endpoints,
        'current_endpoint': state.openai_current_endpoint,
        'current_model': state.openai_current_model
    })


@config_bp.route('/openai/endpoints', methods=['POST'])
def add_openai_endpoint():
    data = request.json
    endpoint_name = data.get('name')
    endpoint_url = data.get('url')
    endpoint_model = data.get('model')

    if not endpoint_name or not endpoint_url:
        return jsonify({'error': '端点名称和URL不能为空'}), 400

    state.openai_endpoints[endpoint_name] = {
        'url': endpoint_url,
        'model': endpoint_model or endpoint_name
    }

    config = load_config()
    config['openai_endpoints'] = state.openai_endpoints
    save_config(config)

    return jsonify({
        'success': True,
        'endpoints': state.openai_endpoints
    })


@config_bp.route('/openai/endpoints/<endpoint_name>', methods=['PUT'])
def update_openai_endpoint(endpoint_name):
    if endpoint_name not in state.openai_endpoints:
        return jsonify({'error': '端点不存在'}), 404

    data = request.json
    endpoint_url = data.get('url')
    endpoint_model = data.get('model')

    if endpoint_url:
        state.openai_endpoints[endpoint_name]['url'] = endpoint_url
    if endpoint_model:
        state.openai_endpoints[endpoint_name]['model'] = endpoint_model

    config = load_config()
    config['openai_endpoints'] = state.openai_endpoints
    save_config(config)

    return jsonify({
        'success': True,
        'endpoints': state.openai_endpoints
    })


@config_bp.route('/openai/endpoints/<endpoint_name>', methods=['DELETE'])
def delete_openai_endpoint(endpoint_name):
    if endpoint_name not in state.openai_endpoints:
        return jsonify({'error': '端点不存在'}), 404

    del state.openai_endpoints[endpoint_name]

    if state.openai_current_endpoint == endpoint_name:
        state.openai_current_endpoint = None
        state.openai_current_model = None

    config = load_config()
    config['openai_endpoints'] = state.openai_endpoints
    config['openai_current_endpoint'] = state.openai_current_endpoint
    config['openai_current_model'] = state.openai_current_model
    save_config(config)

    return jsonify({
        'success': True,
        'endpoints': state.openai_endpoints,
        'current_endpoint': state.openai_current_endpoint,
        'current_model': state.openai_current_model
    })


@config_bp.route('/openai/switch', methods=['POST'])
def switch_openai_endpoint():
    data = request.json
    endpoint_name = data.get('endpoint')

    if endpoint_name not in state.openai_endpoints:
        return jsonify({'error': '端点不存在'}), 404

    state.openai_current_endpoint = endpoint_name
    state.openai_current_model = state.openai_endpoints[endpoint_name]['model']

    config = load_config()
    config['openai_current_endpoint'] = state.openai_current_endpoint
    config['openai_current_model'] = state.openai_current_model
    save_config(config)

    return jsonify({
        'success': True,
        'current_endpoint': state.openai_current_endpoint,
        'current_model': state.openai_current_model
    })


@config_bp.route('/anthropic/endpoints', methods=['GET'])
def get_anthropic_endpoints():
    return jsonify({
        'endpoints': state.anthropic_endpoints,
        'current_endpoint': state.anthropic_current_endpoint,
        'current_model': state.anthropic_current_model
    })


@config_bp.route('/anthropic/endpoints', methods=['POST'])
def add_anthropic_endpoint():
    data = request.json
    endpoint_name = data.get('name')
    endpoint_url = data.get('url')
    endpoint_model = data.get('model')

    if not endpoint_name or not endpoint_url:
        return jsonify({'error': '端点名称和URL不能为空'}), 400

    state.anthropic_endpoints[endpoint_name] = {
        'url': endpoint_url,
        'model': endpoint_model or endpoint_name
    }

    config = load_config()
    config['anthropic_endpoints'] = state.anthropic_endpoints
    save_config(config)

    return jsonify({
        'success': True,
        'endpoints': state.anthropic_endpoints
    })


@config_bp.route('/anthropic/endpoints/<endpoint_name>', methods=['PUT'])
def update_anthropic_endpoint(endpoint_name):
    if endpoint_name not in state.anthropic_endpoints:
        return jsonify({'error': '端点不存在'}), 404

    data = request.json
    endpoint_url = data.get('url')
    endpoint_model = data.get('model')

    if endpoint_url:
        state.anthropic_endpoints[endpoint_name]['url'] = endpoint_url
    if endpoint_model:
        state.anthropic_endpoints[endpoint_name]['model'] = endpoint_model

    config = load_config()
    config['anthropic_endpoints'] = state.anthropic_endpoints
    save_config(config)

    return jsonify({
        'success': True,
        'endpoints': state.anthropic_endpoints
    })


@config_bp.route('/anthropic/endpoints/<endpoint_name>', methods=['DELETE'])
def delete_anthropic_endpoint(endpoint_name):
    if endpoint_name not in state.anthropic_endpoints:
        return jsonify({'error': '端点不存在'}), 404

    del state.anthropic_endpoints[endpoint_name]

    if state.anthropic_current_endpoint == endpoint_name:
        state.anthropic_current_endpoint = None
        state.anthropic_current_model = None

    config = load_config()
    config['anthropic_endpoints'] = state.anthropic_endpoints
    config['anthropic_current_endpoint'] = state.anthropic_current_endpoint
    config['anthropic_current_model'] = state.anthropic_current_model
    save_config(config)

    return jsonify({
        'success': True,
        'endpoints': state.anthropic_endpoints,
        'current_endpoint': state.anthropic_current_endpoint,
        'current_model': state.anthropic_current_model
    })


@config_bp.route('/anthropic/switch', methods=['POST'])
def switch_anthropic_endpoint():
    data = request.json
    endpoint_name = data.get('endpoint')

    if endpoint_name not in state.anthropic_endpoints:
        return jsonify({'error': '端点不存在'}), 404

    state.anthropic_current_endpoint = endpoint_name
    state.anthropic_current_model = state.anthropic_endpoints[endpoint_name]['model']

    config = load_config()
    config['anthropic_current_endpoint'] = state.anthropic_current_endpoint
    config['anthropic_current_model'] = state.anthropic_current_model
    save_config(config)

    return jsonify({
        'success': True,
        'current_endpoint': state.anthropic_current_endpoint,
        'current_model': state.anthropic_current_model
    })
