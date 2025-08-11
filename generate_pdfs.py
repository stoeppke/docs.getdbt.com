import json
import os
import re
import subprocess
import tempfile
import argparse

def extract_all_doc_paths_from_section(sidebar_content, section_key):
    """Extract ALL file paths from a section, including nested categories"""
    paths = []
    
    # Find the section start
    section_start_pattern = f'{section_key}:\\s*\\['
    section_start = re.search(section_start_pattern, sidebar_content)
    if not section_start:
        return paths
    
    # Find the complete section by counting brackets
    start_pos = section_start.end() - 1  # Position of the opening bracket
    bracket_count = 0
    section_end = start_pos
    
    for i, char in enumerate(sidebar_content[start_pos:], start_pos):
        if char == '[':
            bracket_count += 1
        elif char == ']':
            bracket_count -= 1
            if bracket_count == 0:
                section_end = i
                break
    
    section_data = sidebar_content[start_pos:section_end + 1]
    
    # Extract ALL quoted strings that look like document paths
    # This will catch both direct references and nested category items
    all_quotes_pattern = r'"([^"]+)"'
    all_matches = re.findall(all_quotes_pattern, section_data)
    
    for match in all_matches:
        # Filter for actual document paths (not labels, types, etc.)
        if ('/' in match and 
            any(match.startswith(prefix) for prefix in ['docs/', 'reference/', 'best-practices/', 'community/', 'faqs/', 'sql-reference/', 'guides/']) and
            not match.endswith(('.png', '.jpg', '.jpeg', '.gif')) and
            match not in ['type', 'doc', 'category', 'generated-index']):
            paths.append(match)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_paths = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique_paths.append(path)
    
    return unique_paths

def collect_markdown_files_from_directory(directory_path):
    """Collect all markdown files from a directory recursively"""
    markdown_files = []
    
    if not os.path.exists(directory_path):
        return markdown_files
    
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.endswith(('.md', '.mdx')):
                markdown_files.append(os.path.join(root, file))
    
    return sorted(markdown_files)

def discover_sections_dynamically():
    """Dynamically discover available documentation sections"""
    sections = {}
    
    # First, check what directories exist in website/docs/
    docs_path = os.path.join('website', 'docs')
    if os.path.exists(docs_path):
        for item in os.listdir(docs_path):
            item_path = os.path.join(docs_path, item)
            if os.path.isdir(item_path) and not item.startswith('.'):
                # Skip single-file directories or very small collections
                markdown_count = 0
                for root, dirs, files in os.walk(item_path):
                    markdown_count += sum(1 for f in files if f.endswith(('.md', '.mdx')))
                
                # Only include directories with substantial content (more than 2 files)
                if markdown_count > 2:
                    sections[item] = item
    
    # Also try to parse sidebar.js for section keys (these take precedence)
    try:
        with open('website/sidebars.js', 'r') as f:
            sidebar_content = f.read()
        
        # Look for main section definitions in the sidebar structure
        # Match the pattern like "docs: [" or "reference: ["
        section_pattern = r'^\s*(\w+):\s*\['
        matches = re.findall(section_pattern, sidebar_content, re.MULTILINE)
        
        for match in matches:
            # Convert camelCase to kebab-case for directory names
            kebab_name = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', match).lower()
            
            # Special cases
            if match == 'SQLReference':
                kebab_name = 'sql-reference'
            elif match == 'bestPractices':
                kebab_name = 'best-practices'
            
            # Check if this directory actually exists and has content
            dir_path = os.path.join('website', 'docs', kebab_name)
            if os.path.exists(dir_path):
                markdown_count = 0
                for root, dirs, files in os.walk(dir_path):
                    markdown_count += sum(1 for f in files if f.endswith(('.md', '.mdx')))
                
                if markdown_count > 0:
                    sections[match] = kebab_name
                
    except Exception as e:
        print(f"Warning: Could not parse sidebar.js: {e}")
    
    # Filter out any sections that might be duplicates or irrelevant
    filtered_sections = {}
    ignore_list = {'items', 'navigation-options'}  # Common non-content directories
    
    for sidebar_key, section_name in sections.items():
        if section_name not in ignore_list and section_name not in filtered_sections.values():
            filtered_sections[sidebar_key] = section_name
    
    return filtered_sections

def generate_pdfs(sections_to_generate=None):
    output_dir = 'output'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Dynamically discover available sections
    print("🔍 Discovering available documentation sections...")
    available_sections = discover_sections_dynamically()
    
    if not available_sections:
        print("❌ No documentation sections found!")
        return
    
    print(f"📚 Found {len(available_sections)} sections: {', '.join(available_sections.values())}")

    # Read sidebar content for parsing paths
    sidebar_content = ""
    try:
        with open('website/sidebars.js', 'r') as f:
            sidebar_content = f.read()
    except Exception as e:
        print(f"Warning: Could not read sidebar.js: {e}")

    if sections_to_generate:
        sections_to_process = [(k, v) for k, v in available_sections.items() if k in sections_to_generate or v in sections_to_generate]
        if not sections_to_process:
            print(f"❌ No matching sections found for: {sections_to_generate}")
            print(f"Available sections: {', '.join(available_sections.values())}")
            return
    else:
        sections_to_process = list(available_sections.items())

    for sidebar_key, section_name in sections_to_process:
        print(f"Generating PDF for section: {section_name}")
        
        # Use the improved extraction function
        file_paths = extract_all_doc_paths_from_section(sidebar_content, sidebar_key)
        print(f"  Found {len(file_paths)} files from sidebar parsing")
        
        markdown_files = []
        
        # Try to extract files from sidebar first
        for path in file_paths:
            # Clean up path - remove any leading/trailing whitespace
            path = path.strip()
            
            # For SQL reference files, they might need special handling
            if sidebar_key == 'SQLReference' and not path.startswith('sql-reference/'):
                # Handle special SQL reference naming if needed
                path_parts = path.split('/')
                if len(path_parts) > 1 and not path_parts[-1].startswith('sql-'):
                    path_parts[-1] = f"sql-{path_parts[-1]}"
                    path = "/".join(path_parts)

            potential_path_md = os.path.join('website', 'docs', f'{path}.md')
            potential_path_mdx = os.path.join('website', 'docs', f'{path}.mdx')

            if os.path.exists(potential_path_md):
                markdown_files.append(potential_path_md)
            elif os.path.exists(potential_path_mdx):
                markdown_files.append(potential_path_mdx)

        # If no files found from sidebar parsing, try to collect from directory
        if not markdown_files:
            print(f"  No files found from sidebar parsing, trying directory scan...")
            directory_path = os.path.join('website', 'docs', section_name)
            markdown_files = collect_markdown_files_from_directory(directory_path)
            
            if markdown_files:
                print(f"  Found {len(markdown_files)} files by directory scan")

        if not markdown_files:
            print(f"No markdown files found for section: {section_name}")
            continue

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_pdfs = []
            for md_file in markdown_files:
                temp_pdf = os.path.join(temp_dir, f"{os.path.basename(md_file)}.pdf")
                pandoc_command = [
                    'pandoc',
                    md_file,
                    '-o',
                    temp_pdf,
                    '--pdf-engine=weasyprint',
                    '--metadata', f'sourcefile={md_file}',
                    '--lua-filter', 'add-source-link.lua'
                ]
                try:
                    subprocess.run(pandoc_command, check=True, capture_output=True, text=True)
                    temp_pdfs.append(temp_pdf)
                except subprocess.CalledProcessError as e:
                    print(f"Error generating PDF for {md_file}")
                    print(f"Pandoc command: {' '.join(pandoc_command)}")
                    print(f"Pandoc output: {e.stdout}")
                    print(f"Pandoc error: {e.stderr}")

            output_pdf = os.path.join(output_dir, f'{section_name}.pdf')
            if temp_pdfs:
                pdftk_command = ['pdftk'] + temp_pdfs + ['cat', 'output', output_pdf]
                try:
                    subprocess.run(pdftk_command, check=True, capture_output=True, text=True)
                    print(f"Successfully generated {output_pdf}")
                except subprocess.CalledProcessError as e:
                    print(f"Error merging PDFs for section: {section_name}")
                    print(f"pdftk command: {' '.join(pdftk_command)}")
                    print(f"pdftk output: {e.stdout}")
                    print(f"pdftk error: {e.stderr}")

def main():
    parser = argparse.ArgumentParser(description='Generate PDFs from dbt documentation.')
    parser.add_argument('--sections', nargs='+', help='List of sections to generate. Generates all sections if not specified.')
    args = parser.parse_args()

    generate_pdfs(args.sections)

if __name__ == '__main__':
    main()
