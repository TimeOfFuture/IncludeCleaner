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
import time
import clang.cindex
import Utility
reload(sys)
sys.setdefaultencoding('utf-8')


class Task(object):
    def __init__(self, file_path, cleaner):
        # 待处理文件的路径
        self.file_path = file_path
        # 所属的CppIncludeCleaner类
        self.cleaner = cleaner
        # 搜索路径列表
        self.search_path_list = []
        # #include语句字典的字典，{文件名:{行号:相对路径}}
        self.line_include_dict_dict = {}
        # 根据配置不清理的#include语句字典的字典，{文件名:{行号:相对路径}}
        self.line_include_retain_dict_dict = {}
        # 被引用的文件路径集合的字典，{文件名:set()}
        self.referenced_set_dict = {}
        # 因含有其他平台的宏，标记位#include语句不清理的文件集合
        self.macro_retain_set = set()

    def run(self):
        print "Process File:", self.file_path

        # 设置搜索路径
        for search_path in self.cleaner.vcxproj_configuration.vcxproj_search_path_list:
            if search_path not in self.search_path_list:
                self.search_path_list.append(search_path)

        time_list = []
        time_list.append(time.time())

        self.handle_translation_unit(time_list)

        for key in self.referenced_set_dict:
            self.cleaner.node_data[key] = {}
            self.cleaner.node_data[key]["referenced_set"] = self.referenced_set_dict[key]
            if key in self.line_include_dict_dict:
                self.cleaner.node_data[key]["line_include_dict"] = self.line_include_dict_dict[key]
            else:
                self.cleaner.node_data[key]["line_include_dict"] = {}
            if key in self.macro_retain_set:
                self.cleaner.node_data[key]["macro_retain"] = True
            else:
                self.cleaner.node_data[key]["macro_retain"] = False

        self.f_diagnostics.close()
        self.f_debug.close()

    def handle_translation_unit(self, time_list):
        # 生成翻译单元
        tu = self.generate_translation_unit(self.cleaner.vcxproj_configuration)
        Utility.print_or_write_normal(
            "Process For Configuration", self.cleaner.project_configuration, self.f_debug, False, True)
        if not tu:
            print "Generate Translation Unit Fail:", self.file_path
            return False
        time_list.append(time.time())
        Utility.print_or_write_normal(
            "Generate Translation Unit Cost time", time_list[-1] - time_list[-2], self.f_debug, False, True)

        # 解析翻译单元
        if not self.parse_translation_unit(tu, self.cleaner.vcxproj_configuration):
            print "Parse Translation Unit Fail:", self.file_path
            return False
        time_list.append(time.time())
        Utility.print_or_write_normal(
            "Parse Translation Unit Cost time", time_list[-1] - time_list[-2], self.f_debug, False, True)

        return True

    def generate_translation_unit(self, configuration):
        self.index = clang.cindex.Index.create()
        self.f_diagnostics = Utility.make_output_file("diagnostics/", self.file_path, self.cleaner.sln_path)
        self.f_debug = Utility.make_output_file("debug/", self.file_path, self.cleaner.sln_path)

        # 生成宏定义文件
        with open("macro.txt", 'w') as f_macro:
            count = 0
            for key, value in configuration.vcxproj_macro_dict.items():
                count += 1
                if count > 1:
                    f_macro.write("\n")
                if value is not None:
                    f_macro.write("#define " + key + " " + value)
                else:
                    f_macro.write("#define " + key)

        # 生成翻译单元，这里的解析选项不能选默认的0，否则会丢失#include语句相关的信息
        tu_parse_options = clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
        tu = self.index.parse(self.file_path, configuration.clang_arg_list, None, tu_parse_options)

        # 把clang生成AST过程中产生的诊断信息输出一下
        has_error = False
        for diag in tu.diagnostics:
            self.f_diagnostics.write(diag.__repr__() + "\n")
            # 如果有severity >= 3，即error和fatal的diagnostics，则不要继续解析了，反正也是错的
            if diag.severity >= 3:
                has_error = True
        if has_error:
            return None
        else:
            return tu

    def parse_translation_unit(self, tu, configuration):
        cursor = tu.cursor
        cursor_path = Utility.get_abs_path(cursor.displayname, cursor.displayname, configuration)
        self.f_debug.write("Reference records of %s\n" % (cursor_path,))
        for child in cursor.walk_preorder():
            if not child.location.file:
                continue
            if os.path.normcase(child.location.file.name) in self.cleaner.node_data:
                continue

            # 如果遇到其他平台的宏，则标记一下，这个文件中的#include语句不清理
            if child.kind == clang.cindex.CursorKind.MACRO_INSTANTIATION \
                    and child.displayname in self.cleaner.macro_retain:
                Utility.print_or_write_normal("Macro Retain", "%s %s %s %s %s" % (
                    child.displayname, str(child.kind), child.location.line, child.location.column,
                    os.path.normcase(child.location.file.name)), self.f_debug, False, True)
                self.macro_retain_set.add(os.path.normcase(child.location.file.name))

            # 处理#include语句
            self.parse_include(cursor, child, configuration)

            # 处理auto语义定义的自动变量
            self.parse_auto(tu, cursor, child)

            if not child.referenced:
                continue
            if not child.referenced.location.file:
                continue

            # 引用本文件的cursor不用处理
            if child.referenced.location.file.name == child.location.file.name:
                continue

            # 记录符号的声明位置
            if os.path.normcase(child.location.file.name) not in self.referenced_set_dict:
                self.referenced_set_dict[os.path.normcase(child.location.file.name)] = set()
            self.referenced_set_dict[os.path.normcase(child.location.file.name)]\
                .add(os.path.normcase(child.referenced.location.file.name))

        return True

    def parse_include(self, cursor, child, configuration):
        if child.kind == clang.cindex.CursorKind.INCLUSION_DIRECTIVE:
            normcase_file_name = os.path.normcase(child.location.file.name)
            abs_path = Utility.get_abs_path(
                child.displayname, normcase_file_name, configuration)
            if abs_path:
                Utility.print_or_write_normal("Include", "%s %s %s %s %s" % (
                    child.displayname, str(child.kind), child.location.line, child.location.column,
                    normcase_file_name), self.f_debug, False, True)
                if normcase_file_name not in self.line_include_dict_dict:
                    self.line_include_dict_dict[normcase_file_name] = {}
                self.line_include_dict_dict[normcase_file_name][child.location.line] = os.path.normcase(abs_path)
                if os.path.basename(child.displayname) in self.cleaner.include_retain:
                    Utility.print_or_write_normal("Include Retain", "%s %s %s %s %s" % (
                        child.displayname, str(child.kind), child.location.line, child.location.column,
                        normcase_file_name), self.f_debug, False, True)
                    if normcase_file_name not in self.line_include_retain_dict_dict:
                        self.line_include_retain_dict_dict[normcase_file_name] = {}
                    self.line_include_retain_dict_dict[normcase_file_name][child.location.line] \
                        = os.path.normcase(abs_path)

    def parse_auto(self, tu, cursor, child):
        """
        auto语义定义的自动变量是一个很大的坑
        直接遍历clang生成的AST找不到deduced类型
        理论上最简单直接的方法是获取声明的变量或是调用函数返回值的类型对应的Cursor，然而折腾了一天也没找到这样的接口
        所以只能绕个弯路了
        先判断出一个变量是不是auto，然后找到这一行后面所有referenced的cursor
        遍历这些cursor，在他们referenced的cursor的这一行前面所有TYPE_REF类型的cursor都认为是referenced_node
        """
        offset_cursor_list = []
        if child.kind == clang.cindex.CursorKind.VAR_DECL and child.type.kind == clang.cindex.TypeKind.AUTO:
            start_offset = child.location.offset
            offset = start_offset
            while(True):
                offset += 1
                location = clang.cindex.SourceLocation.from_offset(tu, child.location.file, offset)
                offset_cursor = clang.cindex.Cursor.from_location(tu, location)
                if offset_cursor.location.line != child.location.line:
                    return
                if not offset_cursor.referenced:
                    continue
                if offset_cursor.referenced.location.file.name == os.path.normcase(child.location.file.name):
                    continue
                if offset_cursor not in offset_cursor_list:
                    offset_cursor_list.append(offset_cursor)
                    for i in range(offset_cursor.referenced.location.column):
                        type_ref_location = clang.cindex.SourceLocation.from_position(
                            tu, offset_cursor.referenced.location.file, offset_cursor.referenced.location.line, i)
                        type_ref_cursor = clang.cindex.Cursor.from_location(tu, type_ref_location)
                        if type_ref_cursor and type_ref_cursor.kind == clang.cindex.CursorKind.TYPE_REF:
                            if os.path.normcase(child.location.file.name) not in self.referenced_set_dict:
                                self.referenced_set_dict[os.path.normcase(child.location.file.name)] = set()
                            self.referenced_set_dict[os.path.normcase(child.location.file.name)].add(
                                Utility.get_abs_normcase_path(type_ref_cursor.referenced.location.file.name))
