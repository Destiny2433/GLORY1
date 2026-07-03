import os
tpl_dir = 'templates'
for filename in os.listdir(tpl_dir):
    if filename.endswith('.html'):
        filepath = os.path.join(tpl_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove backslashes before single quotes
        content = content.replace("\\'", "'")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
print('Fixed backslash errors in templates.')
