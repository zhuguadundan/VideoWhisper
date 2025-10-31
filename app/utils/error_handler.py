from functools import wraps
from flask import jsonify, request, g
import logging
import traceback

def api_error_handler(f):
    """API端点统一异常处理装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logging.warning(f"ValueError in {f.__name__}: {str(e)}")
            return jsonify({
                'success': False,
                'error': '参数错误',
                'message': str(e)
            }), 400
        except FileNotFoundError as e:
            logging.warning(f"FileNotFoundError in {f.__name__}: {str(e)}")
            return jsonify({
                'success': False,
                'error': '文件未找到',
                'message': str(e)
            }), 404
        except KeyError as e:
            logging.warning(f"KeyError in {f.__name__}: {str(e)}")
            return jsonify({
                'success': False,
                'error': '缺少必要参数',
                'message': f'缺少参数: {str(e)}'
            }), 400
        except ConnectionError as e:
            logging.error(f"ConnectionError in {f.__name__}: {str(e)}")
            return jsonify({
                'success': False,
                'error': '网络连接错误',
                'message': '无法连接到外部服务，请检查网络连接'
            }), 503
        except PermissionError as e:
            logging.error(f"PermissionError in {f.__name__}: {str(e)}")
            return jsonify({
                'success': False,
                'error': '权限错误',
                'message': '没有足够的权限执行此操作'
            }), 403
        except Exception as e:
            # 记录详细错误信息
            logging.exception(f"Unhandled exception in {f.__name__}")
            logging.error(f"Request URL: {request.url}")
            logging.error(f"Request Method: {request.method}")
            logging.error(f"Request Args: {dict(request.args)}")
            if request.is_json:
                try:
                    payload = request.get_json(silent=True) or {}
                    if isinstance(payload, dict):
                        masked = {}
                        for k, v in payload.items():
                            if any(s in k.lower() for s in ['api_key', 'apikey', 'authorization', 'token', 'secret']):
                                masked[k] = '***'
                            else:
                                masked[k] = v
                        logging.error(f"Request JSON (masked): {masked}")
                    else:
                        logging.error("Request JSON present (non-dict)")
                except Exception:
                    logging.error("Request JSON parse error for logging")
            logging.error(traceback.format_exc())
            
            return jsonify({
                'success': False,
                'error': '系统错误',
                'message': f'处理请求时发生错误: {str(e)}',
                'error_type': type(e).__name__
            }), 500
    
    return decorated_function

def safe_json_response(success=True, data=None, message='', error='', status=200):
    """安全的JSON响应构建函数"""
    try:
        response_data = {
            'success': success
        }
        
        if data is not None:
            response_data['data'] = data
        
        if message:
            response_data['message'] = message
            
        if error:
            response_data['error'] = error
        
        # 附加 request_id 元信息（如有）
        try:
            rid = getattr(g, 'request_id', None)
            if rid:
                response_data['meta'] = {'request_id': rid}
        except Exception:
            pass
        return jsonify(response_data), status
    except Exception as e:
        logging.exception(f"Error building JSON response: {str(e)}")
        return jsonify({
            'success': False,
            'error': '响应构建错误',
            'message': '服务器无法构建正确的响应'
        }), 500
