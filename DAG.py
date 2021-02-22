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

import sys
import Utility
reload(sys)
sys.setdefaultencoding('utf-8')


class DAG(object):
    def __init__(self, f_result, cleaner):
        # 用于输出结果的文件句柄
        self.f_result = f_result
        # 所属的IncludeCleaner类
        self.cleaner = cleaner
        # DAG节点字典，{name:node}
        self.name_node_dict = {}
        # DAG的project节点集合
        self.project_node_set = set()
        # DAG的root节点集合
        self.root_node_set = set()
        # DAG的边集合
        self.edge_set = set()
        # DAG的project边集合
        self.project_edge_set = set()
        # DAG中必须要用的边集合
        self.single_way_used_edge_set = set()
        # DAG中可能要用的边集合
        self.multi_way_used_edge_set = set()
        # 遍历中存放节点的栈
        self.dfs_node_stack = []
        # 遍历中已经算过的起止节点字典，{source_node:{dest_node:{single_way_set:set(), multi_way_set:set()}}}
        self.dfs_node_dict = {}
        # 遍历时存放循环引用的节点字典, {source_node:set}
        self.dfs_delay_dict = {}
        # 删除每条边可以减少的RISP字典，{edge:ΔRISP}
        self.edge_risp_dict = {}
        # 可以删除的#include语句字典，{node_name:set()}
        self.to_delete_line_set_dict = {}

    def add_node(self, name, data, is_project_node, is_root_node):
        """增加一个节点

        name为节点名字
        data为节点解析结果数据
        is_project_node为是否是工程内可操作的文件
        is_root_node为是否是根文件
        """

        # 创建节点
        node = DAGNode(name, data, is_project_node, is_root_node)

        # 将节点加入DAG中
        self.name_node_dict[name] = node

        # 如果是project节点，则加入DAG的project节点集合
        if node.is_project_node:
            self.project_node_set.add(node)

        # 如果是root节点，则加入DAG的root节点集合
        if node.is_root_node:
            self.root_node_set.add(node)

        # 将此节点需要的没有在工程文件中定义的节点也加入进来，因为它们虽然不能删减，但是参与了计算
        for node_name in node.need_node_set:
            if node_name not in self.name_node_dict:
                self.add_node(node_name, {'line_include_dict': {}, 'referenced_set': set()}, False, False)

    def pre_process(self):
        """对DAG进行预处理

        通过Node初始化时传入的数据信息构建出Node之间关系
        """

        for from_node in self.name_node_dict.values():
            for line, to_node_name in from_node.line_include_dict.items():
                if to_node_name in self.name_node_dict:
                    to_node = self.name_node_dict[to_node_name]
                    from_node.to_node_set.add(to_node)
                    edge = DAGEdge(line, from_node, to_node)
                    self.edge_set.add(edge)
                    if edge.from_node.is_project_node and edge.to_node.is_project_node:
                        self.project_edge_set.add(edge)
                    from_node.to_edge_dict[to_node] = edge
            from_node.need_node_set = \
                {self.name_node_dict[name] for name in from_node.need_node_set if name in self.name_node_dict}

        print "self.name_node_dict Count:", len(self.name_node_dict)
        print "self.project_node_set Count:", len(self.project_node_set)
        print "self.root_node_set Count:", len(self.root_node_set)
        print "self.edge_set Count:", len(self.edge_set)
        print "self.project_edge_set Count:", len(self.project_edge_set)

    def process(self):
        """解析DAG的主函数

        循环执行贪心算法，每次删掉完全不需要的边和一条能让RISP减少最多的边，直到无边可删为止
        """

        while(True):
            # 从每一个根文件出发进行DFS
            for root_node in self.root_node_set:
                self.DFS(root_node)

            # 计算节点连通所需的必选边集合single_way_set和可选边集合multi_way_set
            for source_node in self.dfs_node_dict:
                for dest_node in self.dfs_node_dict[source_node]:
                    if dest_node in source_node.need_node_set:
                        self.single_way_used_edge_set |= self.dfs_node_dict[source_node][dest_node]["single_way_set"]
                        self.multi_way_used_edge_set |= self.dfs_node_dict[source_node][dest_node]["multi_way_set"]
                        self.multi_way_used_edge_set -= self.single_way_used_edge_set
                    # 如果源节点是根文件，则需计算对应的ΔRISP
                    if source_node.is_root_node:
                        for edge in self.dfs_node_dict[source_node][dest_node]["single_way_set"]:
                            if edge in self.edge_risp_dict:
                                self.edge_risp_dict[edge] += len(dest_node.need_node_set)
                            else:
                                self.edge_risp_dict[edge] = len(dest_node.need_node_set)

            # 计算出完全不需要的边，删掉
            unused_edge_set = self.project_edge_set - self.single_way_used_edge_set - self.multi_way_used_edge_set
            for edge in unused_edge_set:
                if edge.from_node.macro_retain:
                    continue
                Utility.print_or_write_normal("Unused Edge Type1", edge, self.f_result, True, True)
                if edge.from_node.name not in self.to_delete_line_set_dict:
                    self.to_delete_line_set_dict[edge.from_node.name] = set()
                self.to_delete_line_set_dict[edge.from_node.name].add(edge.line)
                self.project_edge_set.remove(edge)
                edge.from_node.to_node_set.remove(edge.to_node)
                del edge.from_node.to_edge_dict[edge.to_node]

            # 从可选边中挑一个能让RISP减少最多的边
            to_delete_edge = None
            to_delete_risp = -1
            for edge in self.multi_way_used_edge_set:
                if edge not in self.project_edge_set:
                    continue
                if edge.from_node.macro_retain:
                    continue
                if edge not in self.edge_risp_dict:
                    continue
                if self.edge_risp_dict[edge] > to_delete_risp:
                    to_delete_edge = edge
                    to_delete_risp = self.edge_risp_dict[edge]

            # 如果上一步算出了一条可以删除的边，那么把这条边删掉，并且说明算法还没有结束，清理一下数据，准备下一次计算
            if to_delete_edge:
                Utility.print_or_write_normal("Unused Edge Type2", to_delete_edge, self.f_result, True, True)
                Utility.print_or_write_normal("Reduce RISP", to_delete_risp, self.f_result, True, True)
                if to_delete_edge.from_node.name not in self.to_delete_line_set_dict:
                    self.to_delete_line_set_dict[to_delete_edge.from_node.name] = set()
                self.to_delete_line_set_dict[to_delete_edge.from_node.name].add(to_delete_edge.line)
                self.project_edge_set.remove(to_delete_edge)
                to_delete_edge.from_node.to_node_set.remove(to_delete_edge.to_node)
                del to_delete_edge.from_node.to_edge_dict[to_delete_edge.to_node]

                self.single_way_used_edge_set.clear()
                self.multi_way_used_edge_set.clear()
                self.dfs_node_stack = []
                self.dfs_node_dict.clear()
                self.dfs_delay_dict.clear()
                self.edge_risp_dict.clear()
            # 如果上一步没有算出一条可以删除的边，说明算法结束了，退出
            else:
                break

    def DFS(self, source_node):
        """深度优先遍历

        遍历计算节点之间的路径信息，存在self.dfs_node_dict中
        """

        # 如果这个节点已经遍历过了，就不重复遍历了
        if source_node in self.dfs_node_dict:
            return
        else:
            self.dfs_node_dict[source_node] = {}

        # 遍历开始将节点入栈
        self.dfs_node_stack.append(source_node)

        for node in source_node.to_node_set:
            if node not in self.dfs_node_stack:
                # 如果这两个节点之间没有进行过计算，说明这条#include语句目前是这两个节点之间唯一的连通路径
                if node not in self.dfs_node_dict[source_node]:
                    self.DFS(node)
                    self.add_edges(source_node, node)
                    self.dfs_node_dict[source_node][node] = {
                        "single_way_set": set([source_node.to_edge_dict[node]]), "multi_way_set": set()}
                # 否则说明这两个节点可以通过其他路径连通，并且这两条路径之间没有公用边
                else:
                    self.dfs_node_dict[source_node][node]["multi_way_set"] |= \
                        self.dfs_node_dict[source_node][node]["single_way_set"]
                    self.dfs_node_dict[source_node][node]["multi_way_set"].add(source_node.to_edge_dict[node])
                    self.dfs_node_dict[source_node][node]["single_way_set"].clear()
            # 这种情况就是循环#include了，需要单独处理，否则会死循环
            else:
                if node not in self.dfs_delay_dict:
                    self.dfs_delay_dict[node] = set()
                self.dfs_delay_dict[node].add(source_node)

        # 单独处理循环#include的情况
        if source_node in self.dfs_delay_dict:
            for node in self.dfs_delay_dict[source_node]:
                self.add_edges(node, source_node)

        # 遍历结束将节点出栈
        self.dfs_node_stack.pop()

    def add_edges(self, from_node, to_node):
        """将from_node到to_node的边加入路径计算

        已知从from_node到to_node有一条边，可以根据to_node的路径信息更新from_node的路径信息
        """
        for dest_node in self.dfs_node_dict[to_node]:
            # 如果from_node到dest_node已经有其他路径了，那么只有在各条路径中都必选的边才是必选边，否则就是可选边
            if dest_node in self.dfs_node_dict[from_node]:
                single_way_set = self.dfs_node_dict[from_node][dest_node]["single_way_set"] \
                    & self.dfs_node_dict[to_node][dest_node]["single_way_set"]
                self.dfs_node_dict[from_node][dest_node]["multi_way_set"] |= \
                    self.dfs_node_dict[from_node][dest_node]["single_way_set"]
                self.dfs_node_dict[from_node][dest_node]["multi_way_set"] |= \
                    self.dfs_node_dict[to_node][dest_node]["single_way_set"]
                self.dfs_node_dict[from_node][dest_node]["multi_way_set"] |= \
                    self.dfs_node_dict[to_node][dest_node]["multi_way_set"]
                self.dfs_node_dict[from_node][dest_node]["multi_way_set"] -= single_way_set
                self.dfs_node_dict[from_node][dest_node]["multi_way_set"].add(from_node.to_edge_dict[to_node])
                self.dfs_node_dict[from_node][dest_node]["single_way_set"] = single_way_set
            # 如果from_node到dest_node没有其他路径，那么把to_node的路径信息拷贝一份，然后把from_node到to_node的边也加进必选边集合
            else:
                self.dfs_node_dict[from_node][dest_node] = {}
                self.dfs_node_dict[from_node][dest_node]["multi_way_set"] = \
                    set(self.dfs_node_dict[to_node][dest_node]["multi_way_set"])
                self.dfs_node_dict[from_node][dest_node]["single_way_set"] = \
                    set(self.dfs_node_dict[to_node][dest_node]["single_way_set"])
                self.dfs_node_dict[from_node][dest_node]["single_way_set"].add(from_node.to_edge_dict[to_node])


class DAGNode(object):
    def __init__(self, name, data, is_project_node, is_root_node):
        # 名字
        self.name = name
        # #include语句字典，{行号:相对路径}
        self.line_include_dict = data['line_include_dict']
        # 此节点#include的节点集合
        self.to_node_set = set()
        # 此节点#include的边字典，{节点:边}
        self.to_edge_dict = {}
        # 需要递归#include进来的节点集合，初始化时是节点路径，在DAG的pre_process函数中变为节点
        self.need_node_set = data['referenced_set']
        # 因含有其他平台的宏，此文件中的#include语句不清理
        self.macro_retain = data["macro_retain"]
        # 是否是project_node
        self.is_project_node = is_project_node
        # 是否是root_node
        self.is_root_node = is_root_node

    def __repr__(self):
        # 为了便于debug，print的时候直接显示name
        return self.name

    def __str__(self):
        # 为了便于debug，用str输出的时候直接显示name
        return self.name

    def __hash__(self):
        # 为了使DAGNode能加入set，能做key，定制一下__hash__函数
        return hash(self.name)


class DAGEdge(object):
    def __init__(self, line, from_node, to_node):
        # #include语句所在的行数
        self.line = line
        # from_node #include 了 to_node
        self.from_node = from_node
        self.to_node = to_node

    def __repr__(self):
        return "The Edge of " + self.from_node.name + " #include " + self.to_node.name

    def __str__(self):
        return "The Edge of " + self.from_node.name + " #include " + self.to_node.name

    def __hash__(self):
        # 为了使DAGEdge能加入set，定制一下__hash__函数
        return hash(self.from_node.name + self.to_node.name)
