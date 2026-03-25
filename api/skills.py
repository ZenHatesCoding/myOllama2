from flask import Blueprint, jsonify
from resources.skills import skill_registry

skills_bp = Blueprint('skills', __name__)

@skills_bp.route('/skills', methods=['GET'])
def get_skills():
    skills = skill_registry.get_all_skills()
    return jsonify({
        'skills': [skill.to_dict() for skill in skills],
        'count': len(skills)
    })


@skills_bp.route('/skills/reload', methods=['POST'])
def reload_skills():
    try:
        skill_registry.reload()
        skills = skill_registry.get_all_skills()
        return jsonify({
            'success': True,
            'message': f'成功加载 {len(skills)} 个 Skill',
            'skills': [skill.to_dict() for skill in skills]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@skills_bp.route('/skills/<skill_name>', methods=['GET'])
def get_skill_detail(skill_name):
    skill = skill_registry.get_skill(skill_name)
    if not skill:
        return jsonify({'error': 'Skill 不存在'}), 404

    return jsonify({
        'name': skill.name,
        'description': skill.description,
        'has_scripts': skill.has_scripts(),
        'has_references': skill.has_references(),
        'content': skill.get_full_content()
    })
