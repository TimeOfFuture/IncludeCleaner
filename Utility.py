#!/usr/bin/python
# -*- coding: UTF-8 -*-

'''
 Copyright (c) 2020-2021 翁轩锴 wengxuankai@foxmail.com

 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:

 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 THE SOFTWARE.
'''

import os
import sys
reload(sys)
sys.setdefaultencoding('utf-8')


def get_abs_normcase_path(path):
    return os.path.normcase(os.path.abspath(path))


def get_abs_path(path, file_path, configuration):
    '''
    取得path的绝对路径
    先在file_path的同层目录中找，找不到则在configuration中设置的搜索路径中找
    '''

    abs_path = get_abs_join_path(file_path + "\\..", path)
    if os.path.isfile(abs_path):
        return abs_path

    for search_path in configuration.vcxproj_search_path_list:
        abs_path = get_abs_join_path(search_path, path)
        if os.path.isfile(abs_path):
            return abs_path


def get_rel_path(path, search_path_list):
    '''
    取得path的相对路径
    以search_path_list中的路径为起点
    '''

    for search_path in search_path_list:
        rel_path = os.path.relpath(path, search_path)
        if ".." not in rel_path:
            return rel_path.replace("\\", "/")


def get_abs_join_path(path1, path2):
    '''
    取path1和path2合并后的绝对路径
    '''

    return os.path.abspath(os.path.join(path1, path2))


def make_output_file(path1, path2, path3):
    '''
    在path1下创建一个path2相对于path3的相对路径的文件
    '''

    path = os.path.join(path1, os.path.relpath(path2, path3).replace("..\\", ""))
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    return open(path + ".txt", 'w')


def print_or_write_normal(title, var, f_result, enable_print, enable_write):
    '''
    打印或写入一个普通的值
    '''

    if enable_print:
        print "\n%s:%s" % (title, str(var))
    if enable_write:
        f_result.write("\n%s:%s\n" % (title, str(var)))


def print_or_write_dict(title, dic, f_result, enable_print, enable_write):
    '''
    打印或写入一个字典
    '''

    if enable_print:
        print "\n%s:\n" % (title,)
        for key, value in dic.items():
            print "%s:%s" % (str(key), str(value))
    if enable_write:
        f_result.write("\n%s:\n" % (title,))
        for key, value in dic.items():
            f_result.write("%s:%s\n" % (str(key), str(value)))


def print_or_write_detailed_node_set(title, node_set, f_result, enable_print, enable_write):
    '''
    打印或写入一个节点的详细数据
    '''

    if enable_print:
        print "\n%s:" % (title,)
        for node in node_set:
            print "%s\n%s%s\n%s%s\n%s%s" \
                % (str(node), "subroot_set: ", str(node.subroot_set), "source_set: ", str(node.source_set),
                    "recursive_source_set: ", str(node.recursive_source_set))
    if enable_write:
        f_result.write("\n%s:\n" % (title,))
        for node in node_set:
            f_result.write("%s\n%s%s\n%s%s\n%s%s\n" % (
                str(node), "subroot_set: ", str(node.subroot_set), "source_set: ", str(node.source_set),
                "recursive_source_set: ", str(node.recursive_source_set)))
