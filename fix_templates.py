import os, re

tpl_dir = 'templates'
for filename in os.listdir(tpl_dir):
    if filename.endswith('.html'):
        filepath = os.path.join(tpl_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace style.css
        content = re.sub(r'href="style\.css"', 'href="{{ url_for(\'static\', filename=\'style.css\') }}"', content)
        
        # Replace script.js
        content = re.sub(r'src="script\.js"', 'src="{{ url_for(\'static\', filename=\'script.js\') }}"', content)
        
        # Replace images/ prefix in img tags
        content = re.sub(r'src="images/([^"]+)"', r'src="{{ url_for(\'static\', filename=\'images/\1\') }}"', content)
        
        # Replace images/ for favicons or og:image
        content = re.sub(r'href="images/([^"]+)"', r'href="{{ url_for(\'static\', filename=\'images/\1\') }}"', content)
        content = re.sub(r'content="images/([^"]+)"', r'content="{{ url_for(\'static\', filename=\'images/\1\') }}"', content)

        # Replace download.webp
        content = content.replace('src="download.webp"', 'src="{{ url_for(\'static\', filename=\'images/download.webp\') }}"')

        # Fix gallery.html links (just in case they missed)
        content = content.replace('href="galley.html"', 'href="{{ url_for(\'gallery\') }}"')
        
        # Replace other HTML links
        content = content.replace('href="About.html"', 'href="{{ url_for(\'about\') }}"')
        content = content.replace('href="about.html"', 'href="{{ url_for(\'about\') }}"')
        content = content.replace('href="support.html"', 'href="{{ url_for(\'support\') }}"')
        content = content.replace('href="volunteer.html"', 'href="{{ url_for(\'volunteer\') }}"')
        content = content.replace('href="gallery.html"', 'href="{{ url_for(\'gallery\') }}"')

        # Ensure index.html references
        content = content.replace('href="index.html"', 'href="{{ url_for(\'index\') }}"')

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
print('HTML templates updated for static assets.')
