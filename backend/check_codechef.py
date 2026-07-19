with open("page.html", "r", encoding="utf-8") as f:
    html = f.read()

import re

# Print from rating-data-section problems-solved to the end of the section
match = re.search(r'<section class="rating-data-section problems-solved">.*?</section>', html, re.DOTALL)
if match:
    print("Section content:")
    print(match.group(0)[:1500])
else:
    print("problems-solved section not matched")
