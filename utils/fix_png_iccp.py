#!/usr/bin/env python3
"""
PNG iCCP 配置文件修复工具

用于扫描并修复PNG文件中的iCCP色彩配置文件问题。
libpng警告 "known incorrect sRGB profile" 是由于PNG文件中的iCCP chunk
包含非标准/过时的ICC配置文件导致的。

本工具使用Pillow重新保存PNG文件，自动去除有问题的iCCP chunk，
从根本上修复libpng警告问题。
"""

import os
import sys
from pathlib import Path
from PIL import Image
import io


def fix_png_iccp(input_path: str, output_path: str = None, quality: int = 95) -> bool:
    """
    修复PNG文件的iCCP配置问题
    
    Args:
        input_path: 输入PNG文件路径
        output_path: 输出PNG文件路径（如果为None，则覆盖原文件）
        quality: PNG质量（仅对某些格式有效）
    
    Returns:
        bool: 修复是否成功
    """
    try:
        with Image.open(input_path) as img:
            img_info = img.info.copy()
            
            if output_path is None:
                output_path = input_path
            
            output_buffer = io.BytesIO()
            img.save(output_buffer, format='PNG', optimize=True)
            output_buffer.seek(0)
            
            with open(output_path, 'wb') as f:
                f.write(output_buffer.getvalue())
            
            return True
            
    except Exception as e:
        print(f"修复失败 {input_path}: {e}")
        return False


def scan_and_fix_directory(directory: str, extensions: list = None, dry_run: bool = False) -> dict:
    """
    扫描目录下的所有PNG文件并修复iCCP问题
    
    Args:
        directory: 要扫描的目录
        extensions: 要检查的文件扩展名列表
        dry_run: 如果为True，只扫描不修复
    
    Returns:
        dict: 扫描结果统计
    """
    if extensions is None:
        extensions = ['.png']
    
    results = {
        'total': 0,
        'fixed': 0,
        'failed': 0,
        'skipped': 0,
        'files': []
    }
    
    directory_path = Path(directory)
    if not directory_path.exists():
        print(f"目录不存在: {directory}")
        return results
    
    for ext in extensions:
        for file_path in directory_path.rglob(f'*{ext}'):
            results['total'] += 1
            
            relative_path = file_path.relative_to(directory_path.parent)
            print(f"\n检查: {relative_path}")
            
            try:
                with Image.open(file_path) as img:
                    iccp = img.info.get('icc_profile')
                    
                    if iccp:
                        print(f"  - 找到iCCP配置, 大小: {len(iccp)} bytes")
                        
                        if dry_run:
                            print(f"  - [DRY RUN] 将修复此文件")
                            results['skipped'] += 1
                        else:
                            if fix_png_iccp(str(file_path)):
                                print(f"  - 已修复!")
                                results['fixed'] += 1
                            else:
                                print(f"  - 修复失败!")
                                results['failed'] += 1
                    else:
                        print(f"  - 无iCCP配置")
                        results['skipped'] += 1
                        
            except Exception as e:
                print(f"  - 处理错误: {e}")
                results['failed'] += 1
    
    return results


def check_single_file(file_path: str) -> dict:
    """
    检查单个PNG文件的iCCP配置
    
    Args:
        file_path: PNG文件路径
    
    Returns:
        dict: 检查结果
    """
    result = {
        'path': file_path,
        'has_iccp': False,
        'iccp_size': 0,
        'error': None
    }
    
    try:
        with Image.open(file_path) as img:
            iccp = img.info.get('icc_profile')
            
            if iccp:
                result['has_iccp'] = True
                result['iccp_size'] = len(iccp)
                print(f"文件: {file_path}")
                print(f"  包含iCCP配置, 大小: {len(iccp)} bytes")
            else:
                print(f"文件: {file_path}")
                print(f"  无iCCP配置")
                
    except Exception as e:
        result['error'] = str(e)
        print(f"检查失败: {e}")
    
    return result


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='PNG iCCP配置修复工具')
    parser.add_argument('path', nargs='?', help='要处理的文件或目录路径')
    parser.add_argument('--dry-run', action='store_true', help='仅扫描不修复')
    parser.add_argument('--check', action='store_true', help='仅检查文件iCCP配置')
    parser.add_argument('--fix', action='store_true', help='修复PNG文件的iCCP问题')
    parser.add_argument('--extensions', nargs='+', default=['.png'], help='要处理的文件扩展名')
    
    args = parser.parse_args()
    
    if not args.path:
        parser.print_help()
        sys.exit(1)
    
    path = Path(args.path)
    
    if args.check:
        if path.is_file():
            check_single_file(str(path))
        elif path.is_dir():
            print(f"扫描目录: {path}")
            results = scan_and_fix_directory(str(path), args.extensions, dry_run=True)
            print(f"\n=== 扫描结果 ===")
            print(f"总文件数: {results['total']}")
            print(f"包含iCCP: {results['total'] - results['skipped']}")
            print(f"无需修复: {results['skipped']}")
        else:
            print(f"路径无效: {path}")
            sys.exit(1)
    
    elif args.fix:
        if path.is_file():
            print(f"修复文件: {path}")
            if fix_png_iccp(str(path)):
                print("修复成功!")
            else:
                print("修复失败!")
                sys.exit(1)
        elif path.is_dir():
            print(f"修复目录: {path}")
            results = scan_and_fix_directory(str(path), args.extensions, dry_run=args.dry_run)
            print(f"\n=== 修复结果 ===")
            print(f"总文件数: {results['total']}")
            print(f"已修复: {results['fixed']}")
            print(f"失败: {results['failed']}")
            print(f"跳过: {results['skipped']}")
        else:
            print(f"路径无效: {path}")
            sys.exit(1)
    
    else:
        parser.print_help()
