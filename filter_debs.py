import os
import glob
import subprocess
import re
import sys

def main():
    debs_dir = 'output'
    build_bootstraps_path = 'scripts/build-bootstraps.sh'

    if not os.path.exists(build_bootstraps_path):
        print(f"Error: {build_bootstraps_path} not found.")
        sys.exit(1)

    # 1. Parse build-bootstraps.sh to find all explicitly built packages
    with open(build_bootstraps_path, 'r') as f:
        script_content = f.read()

    # Extract all PACKAGES+=("name") or PACKAGES+=('name')
    explicit_packages = set(re.findall(r'PACKAGES\+=\(\s*["\']([^"\']+)["\']\s*\)', script_content))
    print("Explicit packages to build:", explicit_packages)

    # 2. Read package metadata from all .deb files in output/
    package_to_file = {}
    dependencies = {}

    deb_files = glob.glob(os.path.join(debs_dir, '*.deb'))
    for deb in deb_files:
        # Run dpkg-deb to get Package name
        res_pkg = subprocess.run(['dpkg-deb', '-f', deb, 'Package'], capture_output=True, text=True)
        pkg_name = res_pkg.stdout.strip()
        if not pkg_name:
            continue
        
        package_to_file[pkg_name] = deb
        
        # Run dpkg-deb to get Depends
        res_deps = subprocess.run(['dpkg-deb', '-f', deb, 'Depends'], capture_output=True, text=True)
        deps_str = res_deps.stdout.strip()
        
        # Parse dependencies
        deps_list = []
        if deps_str:
            # Depends looks like: libc++, libbz2, liblzma (>= 5.2.0)
            # Split by comma
            for dep in deps_str.split(','):
                dep = dep.strip()
                if not dep:
                    continue
                # Split by space to remove version info, e.g. "libc++ (>= 1.0)" -> "libc++"
                dep_name = dep.split(' ')[0]
                # Split by '(' to remove version info without space, e.g. "libc++(>=1.0)" -> "libc++"
                dep_name = dep_name.split('(')[0]
                # Split by '|' to handle alternatives, taking the first one
                dep_name = dep_name.split('|')[0].strip()
                deps_list.append(dep_name)
                
        dependencies[pkg_name] = deps_list

    # 3. Recursively find all transitively required packages starting from explicit_packages
    required_packages = set()
    queue = list(explicit_packages)

    # We also explicitly include "libbz2" because "bzip2" is built as a subpackage of "libbz2"
    # and we want to keep both.
    if "bzip2" in explicit_packages or "libbz2" in explicit_packages:
        queue.append("bzip2")
        queue.append("libbz2")

    while queue:
        pkg = queue.pop(0)
        if pkg in required_packages:
            continue
        
        if pkg in package_to_file:
            required_packages.add(pkg)
            for dep in dependencies.get(pkg, []):
                if dep not in required_packages:
                    queue.append(dep)

    # Add any explicit package that exists in output to the required set
    for pkg in explicit_packages:
        if pkg in package_to_file:
            required_packages.add(pkg)

    print("Required packages (count: {}):".format(len(required_packages)), required_packages)

    # 4. Remove any .deb file that is not required
    deleted_count = 0
    for pkg_name, deb_path in list(package_to_file.items()):
        if pkg_name not in required_packages:
            print(f"Removing unused dependency: {pkg_name} ({deb_path})")
            try:
                os.remove(deb_path)
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete {deb_path}: {e}")

    print(f"Cleanup complete. Deleted {deleted_count} unused .deb files.")

if __name__ == '__main__':
    main()
