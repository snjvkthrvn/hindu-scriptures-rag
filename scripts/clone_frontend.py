import os
import shutil
import re

def clean_jinja_html(content, register_mode=False, beta_mode=False):
    # 1. Replace csrf_token()
    content = content.replace("{{ csrf_token() }}", "dummy-csrf-token")
    
    # 2. Replace url_for for static files
    # Examples:
    # {{ url_for('static', filename='css/style.css') }} -> static/css/style.css
    # {{ url_for('beta.static', filename='css/style.css') }} -> static/css/style.css
    content = re.sub(r"\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}", r"static/\1", content)
    content = re.sub(r"\{\{\s*url_for\('beta\.static',\s*filename='([^']+)'\)\s*\}\}", r"static/\1", content)
    
    # 3. Replace data-api-base="{{ api_base|default('') }}" -> data-api-base=""
    content = content.replace("{{ api_base|default('') }}", "")
    
    # 4. Handle open_registration conditional blocks
    # We will keep the signup/registration button for design review
    content = re.sub(r"\{%\s*if\s+open_registration\s*%\}(.*?)\{%\s*endif\s*%\}", r"\1", content, flags=re.DOTALL)
    
    # 5. Handle register_mode conditionals for login/register pages
    if "{% if register_mode %}" in content:
        if register_mode:
            # Keep register parts, remove login parts
            # e.g., {% if register_mode %}Create account{% else %}Sign in{% endif %}
            content = re.sub(r"\{%\s*if\s+register_mode\s*%\}(.*?)\{%\s*else\s*%\}(.*?)\{%\s*endif\s*%\}", r"\1", content, flags=re.DOTALL)
            content = re.sub(r"\{%\s*if\s+not\s+register_mode\s+and\s+open_registration\s*%\}(.*?)\{%\s*endif\s*%\}", "", content, flags=re.DOTALL)
            content = re.sub(r"\{%\s*if\s+register_mode\s*%\}(.*?)\{%\s*endif\s*%\}", r"\1", content, flags=re.DOTALL)
        else:
            # Keep login parts, remove register parts
            content = re.sub(r"\{%\s*if\s+register_mode\s*%\}(.*?)\{%\s*else\s*%\}(.*?)\{%\s*endif\s*%\}", r"\2", content, flags=re.DOTALL)
            # handle {% if not register_mode and open_registration %}
            content = re.sub(r"\{%\s*if\s+not\s+register_mode\s+and\s+open_registration\s*%\}(.*?)\{%\s*endif\s*%\}", r"\1", content, flags=re.DOTALL)
            content = re.sub(r"\{%\s*if\s+register_mode\s*%\}(.*?)\{%\s*endif\s*%\}", "", content, flags=re.DOTALL)

    # 6. Replace action URLs in forms
    content = re.sub(r'action="\{%.*?%\}"', 'action="#"', content)
    
    # 7. Replace back button url: {{ next_url|safe_next_path }} -> index.html
    content = content.replace("{{ next_url|safe_next_path }}", "index.html")
    content = re.sub(r"\{\{\s*url_for\('auth\.register',\s*next=next_url\)\s*\}\}", "register.html", content)
    content = re.sub(r"\{\{\s*url_for\('auth\.login',\s*next=next_url\)\s*\}\}", "login.html", content)
    
    # 7.1. Replace absolute auth paths with static pages for static preview
    content = content.replace('href="/auth/register"', 'href="register.html"')
    content = content.replace('href="/auth/login"', 'href="login.html"')
    
    # 8. Clean up any remaining {% if error %}, {% if google_oauth_enabled %}
    content = re.sub(r"\{%\s*if\s+error\s*%\}(.*?)\{%\s*endif\s*%\}", "", content, flags=re.DOTALL)
    content = re.sub(r"\{%\s*if\s+google_oauth_enabled\s*%\}(.*?)\{%\s*endif\s*%\}", r"\1", content, flags=re.DOTALL)
    content = re.sub(r"\{\{\s*url_for\('auth\.google_login',\s*next=next_url\)\s*\}\}", "#google-login", content)
    
    # 9. Clean up any raw variables like {{ email }} or {{ request.form.get(...) }}
    content = re.sub(r"\{\{\s*request\.form\.get\([^)]+\)\s*\}\}", "", content)
    content = content.replace("{{ next_url | e }}", "index.html")
    
    # 10. Clean up any leftover {% if/for/else/endif/endfor %} statements
    content = re.sub(r"\{%.*?%\}", "", content)
    content = re.sub(r"\{\{.*?\}\}", "", content)
    
    return content

def clone_app(src_dir, dest_dir, is_beta=False):
    print(f"Cloning {src_dir} to {dest_dir}...")
    os.makedirs(dest_dir, exist_ok=True)
    
    # Copy static assets
    src_static = os.path.join(src_dir, "static")
    dest_static = os.path.join(dest_dir, "static")
    if os.path.exists(src_static):
        shutil.copytree(src_static, dest_static, dirs_exist_ok=True)
        print(f"  Copied static folder")
    
    # Process templates
    src_templates = os.path.join(src_dir, "templates")
    
    # Locate index.html
    index_path = os.path.join(src_templates, "beta", "index.html") if is_beta else os.path.join(src_templates, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        cleaned_html = clean_jinja_html(html, beta_mode=is_beta)
        with open(os.path.join(dest_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(cleaned_html)
        print(f"  Processed index.html")
        
    # Locate login.html
    login_path = os.path.join(src_templates, "login.html")
    if os.path.exists(login_path):
        with open(login_path, "r", encoding="utf-8") as f:
            html = f.read()
        
        # Compile as login.html
        login_html = clean_jinja_html(html, register_mode=False, beta_mode=is_beta)
        with open(os.path.join(dest_dir, "login.html"), "w", encoding="utf-8") as f:
            f.write(login_html)
        print(f"  Processed login.html")
        
        # Compile as register.html
        register_html = clean_jinja_html(html, register_mode=True, beta_mode=is_beta)
        with open(os.path.join(dest_dir, "register.html"), "w", encoding="utf-8") as f:
            f.write(register_html)
        print(f"  Processed register.html")

def main():
    workspace = "D:\\hindu-scriptures-rag"
    target_root = os.path.join(workspace, "frontend-clone")
    
    # 1. Main frontend
    main_src = os.path.join(workspace, "scripts", "rag")
    main_dest = os.path.join(target_root, "main")
    clone_app(main_src, main_dest, is_beta=False)
    
    # 2. English Beta frontend
    beta_src = os.path.join(workspace, "english-v1-rag")
    beta_dest = os.path.join(target_root, "english-beta")
    clone_app(beta_src, beta_dest, is_beta=True)
    
    print("Frontend cloning and template compilation complete!")

if __name__ == "__main__":
    main()
