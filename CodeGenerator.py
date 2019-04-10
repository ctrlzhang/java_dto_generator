#!/usr/bin/env python
# coding=utf-8
import os

import time

import xlrd

import CodeTemplate

from LogTool import logger

from CamelTransformTool import CamelTransformTool

import TypeDict

from ExcelConf import excel_conf

import Target

import sys

import Constant

from ErrorUtil import ErrorUtil

from CommonUtil import CommonUtil

from FileWriter import FileWriter

reload(sys)
sys.setdefaultencoding('utf-8')


class CodeGenerator(object):
    """
    代码生成工具
    """

    service_name = "default"

    def __init__(self):
        pass

    @staticmethod
    def gen_code(sheet, target):
        """
        实际处理逻辑, 抽取出来方便复用
        :param target: 目标目录
        :param sheet: 包含sheet名称、sheet所拥有的数据
        """
        dir_path = CodeTemplate.java_template.get("default_file_path").get(
                "output_" + target) % CodeGenerator.service_name
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        fp = open(dir_path + sheet.get("sheet_name") + ".java", "w+")
        CodeGenerator.gen_copyright(fp)
        CodeGenerator.gen_package_name(fp)
        CodeGenerator.gen_import(fp, sheet.get("need_import_module"))
        CodeGenerator.gen_body(fp, sheet)
        fp.close()

    @staticmethod
    def run(target):
        """
        依次生成代码
        :param target: 服务对象
        """
        protocol_data = CodeGenerator.init(target)

        for sheet in protocol_data:
            CodeGenerator.gen_code(sheet, target)

    @staticmethod
    def init(target):
        """
        解析excel文件，收集要处理的数据, 为target目标对象生成dto
        :param target: 目标对象有:openapi\pmbank\通用
        """
        protocol_file = CodeTemplate.java_template.get("protocol_file")
        if os.path.isfile(protocol_file):
            excel_data = xlrd.open_workbook(protocol_file)
            sheets = excel_data.sheets()
            sheet_names = excel_data.sheet_names()
            sheet_num = len(sheets)

            if 0 >= sheet_num:
                logger.error("data not found in excel")
                return

            index = 0
            protocol_data = []
            while index < sheet_num:
                dto_num = 0
                need_import_module = []
                sheet_origin_name = sheet_names[index].strip()
                # 从excel读到的sheet名称,为unicode格式, 需转换为utf-8编码
                sheet_origin_name = sheet_origin_name.encode('utf-8')
                sheet_name = excel_conf.get("sheets_name_dict").get(sheet_origin_name)
                if sheet_name is None:
                    index += 1
                    logger.warn("sheet_name=%s not in dict, no need to parse" % sheet_origin_name)
                    continue

                content = {
                    "sheet_name": sheet_name,
                    "dto_elems": [],
                    "need_import_module": [],
                }
                table = sheets[index]
                nrows = table.nrows

                # 加载excel描述规则
                row_format = excel_conf.get("sheets_row_format")
                if row_format is None:
                    logger.error("miss option sheets_row_format")
                    return

                min_field_num = row_format.get("field_min_num")
                if min_field_num is None:
                    logger.error("miss option field_min_num")
                    return

                field_pos = excel_conf.get("sheets_field_position")
                if field_pos is None:
                    logger.error("miss option sheets_field_position")
                    return

                pos_id = field_pos.get("field_id")
                pos_name = field_pos.get("field_name")
                pos_comment = field_pos.get("field_comment")
                pos_type = field_pos.get("field_type")

                if pos_id is None or pos_name is None or pos_type is None:
                    logger.error("miss field_id or field_name or field_type in sheets_field_position")
                    return

                # 用于内嵌的文件
                nest_dto_filename = ""
                nest_dto_fp = ""
                nest_dto_elems = []
                nest_dto_import_module = []
                lv2_nest_dto_filename = ""
                lv2_nest_dto_fp = ""
                lv2_nest_dto_elems = []
                lv2_nest_dto_import_module = []

                # 公共的解析逻辑，基于excel描述规则
                for i in xrange(nrows):

                    # 默认不需要生成嵌套的dto, 目前只支持2层嵌套
                    need_create_nest_dto = False
                    lv2_need_create_nest_dto = False

                    data = table.row_values(i)
                    if len(data) < min_field_num:
                        logger.warn("sheet_name=%s row=%s miss some cols, you need at least %s cols" % (
                            sheet_name, i, min_field_num))
                        continue

                    # 字段位置id
                    print type(data[pos_id])
                    dto_field_id = data[pos_id]
                    print dto_field_id
                    if data[pos_id] is None:
                        logger.error("sheet_name=%s row=%s miss field_id" % (sheet_origin_name, i))
                        ErrorUtil.addInvalidFieldId(target, sheet_name,
                                                    data[pos_name] if data[pos_name] is not None else "unknown")
                    elif type(data[pos_id]) == int or str(data[pos_id]).strip().isdigit():
                        dto_field_id = int(data[pos_id])
                    elif type(data[pos_id]) == float:
                        if CommonUtil.isFloat(dto_field_id):
                            # 如果确实为浮点数, 则意味着需要生成嵌套的dto
                            need_create_nest_dto = True
                    else:
                        tmp = str(data[pos_id]).strip()
                        dot_count = tmp.count('.')
                        if dot_count == 1:
                            need_create_nest_dto = True
                        elif dot_count == 2:
                            need_create_nest_dto = True
                            lv2_need_create_nest_dto = True
                        else:
                            print type(data[pos_id])
                            continue

                    # 一层嵌套是否需要退出
                    if not need_create_nest_dto and not CommonUtil.is_empty(nest_dto_fp):
                        nest_dto_content = {
                            "sheet_name": nest_dto_filename,
                            "dto_elems": nest_dto_elems,
                            "need_import_module": nest_dto_import_module,
                        }
                        CodeGenerator.gen_code(nest_dto_content, target)

                    # 二层嵌套是否需要退出
                    if not lv2_need_create_nest_dto and not CommonUtil.is_empty(lv2_nest_dto_fp):
                        lv2_nest_dto_content = {
                            "sheet_name": lv2_nest_dto_filename,
                            "dto_elems": lv2_nest_dto_elems,
                            "need_import_module": lv2_nest_dto_import_module,
                        }
                        CodeGenerator.gen_code(lv2_nest_dto_content, target)

                    # 字段名校验
                    if CommonUtil.is_empty(data[pos_name]):
                        logger.error("sheet_name=%s have empty field_name, please check" % sheet_origin_name)
                        ErrorUtil.addEmptyFieldName(target)
                        continue

                    dto_field_name = str(data[pos_name]).strip()
                    dto_field_type = str(CodeTemplate.java_template.get("default_field_type") if CommonUtil.is_empty(
                            data[pos_type]) else data[pos_type]).strip()

                    # 字段类型校验--预处理完还是没有, 则过滤该行
                    if CommonUtil.is_empty(dto_field_type):
                        ErrorUtil.addInvalidFieldType(target, sheet_name, dto_field_name)
                        continue

                    # 特殊处理(
                    pos = dto_field_type.find('(')
                    if pos > 0:
                        dto_field_type = dto_field_type[0:pos]

                    # 字段类型二次校验 -- 检查以'('号开始的类型
                    if 0 == pos:
                        ErrorUtil.addInvalidFieldType(target, sheet_name, dto_field_name)

                    # 字段注释
                    dto_field_comment = str("" if data[pos_comment] is None else data[pos_comment]).strip()

                    # 当读到字段id为1，且当前尚未生成过Dto时，需
                    # 1.更新sheet_name
                    # 2.dto计数加1
                    # 当读到字段id为1，且已生成过dto时，需
                    # 1.将已有的content内容加入protocol_data中
                    # 2.初始化content
                    if 1 == dto_field_id:
                        if 0 == dto_num:
                            content["sheet_name"] = sheet_name + CodeTemplate.java_template.get(
                                    "default_request_filename_postfix")
                            dto_num += 1
                            CodeGenerator.setRequestPropertyStyle(target)

                        else:
                            content["need_import_module"] = need_import_module
                            need_import_module = []
                            CodeGenerator.gen_code(content, target)
                            content["sheet_name"] = sheet_name + CodeTemplate.java_template.get(
                                    "default_response_filename_postfix")
                            content["dto_elems"] = []
                            content["need_import_module"] = []
                            CodeGenerator.setResponsePropertyStyle(target)

                    # 是否包含list类型字段
                    tmp_type = dto_field_type.lower()
                    if tmp_type in ["list", "array"]:
                        if lv2_need_create_nest_dto and "list" not in lv2_nest_dto_import_module:
                            lv2_nest_dto_import_module.append("list")
                        elif need_create_nest_dto and "list" not in nest_dto_import_module:
                            nest_dto_import_module.append("list")
                        else:
                            if "list" not in need_import_module:
                                need_import_module.append("list")

                        dir_path = CodeTemplate.java_template.get("default_file_path").get(
                            "output_" + target) % CodeGenerator.service_name
                        if not os.path.exists(dir_path):
                            os.makedirs(dir_path)

                        # 为Array、List字段生成独立的dto文件
                        # 并使后续的小数点字段进入该dto内部
                        # 不支持嵌套array的情况, 所以这里只有为false时，才会生成dto, 否则前面生成的数据会被覆盖
                        if not need_create_nest_dto:
                            nest_dto_filename = CamelTransformTool.trans_underline_field_to_camel_classname(
                                    dto_field_name) + "DTO"
                            nest_dto_fp = open(dir_path + nest_dto_filename + ".java", "w+")
                            nest_dto_elems = []
                            nest_dto_import_module = []
                        elif not lv2_need_create_nest_dto:
                            lv2_nest_dto_filename = CamelTransformTool.trans_underline_field_to_camel_classname(
                                    dto_field_name) + "DTO"
                            lv2_nest_dto_fp = open(dir_path + lv2_nest_dto_filename + ".java", "w+")
                            lv2_nest_dto_elems = []
                            lv2_nest_dto_import_module = []

                    # 是否包含date类型
                    if tmp_type in ["t", "d", "date"]:
                        if lv2_need_create_nest_dto and "date" not in lv2_nest_dto_import_module:
                            lv2_nest_dto_import_module.append("date")
                        elif need_create_nest_dto and "date" not in nest_dto_import_module:
                            nest_dto_import_module.append("date")
                        else:
                            if "date" not in need_import_module:
                                need_import_module.append("date")

                    # 是否包含decimal类型
                    if tmp_type in ["b", "decimal", "bigdecimal"]:
                        if lv2_need_create_nest_dto and "big_decimal" not in lv2_nest_dto_import_module:
                            lv2_nest_dto_import_module.append("big_decimal")
                        elif need_create_nest_dto and "big_decimal" not in nest_dto_import_module:
                            nest_dto_import_module.append("big_decimal")
                        else:
                            if "big_decimal" not in need_import_module:
                                need_import_module.append("big_decimal")

                    if dto_field_name is None or dto_field_type is None:
                        logger.error("dto_field_name or dto_field_type miss, please check you protocol file")
                        continue

                    dto_elem = {
                        "name": dto_field_name,
                        "type": dto_field_type,
                        "comment": dto_field_comment,
                    }

                    # 如果是嵌套的,则进入嵌套文件DTO中
                    if lv2_need_create_nest_dto:
                        lv2_nest_dto_elems.append(dto_elem)
                    elif need_create_nest_dto:
                        nest_dto_elems.append(dto_elem)
                    else:
                        content["dto_elems"].append(dto_elem)

                # 单个sheet处理结束后,把未生成的文件生成出来
                # 一层嵌套
                if need_create_nest_dto and not CommonUtil.is_empty(nest_dto_fp):
                    nest_dto_content = {
                        "sheet_name": nest_dto_filename,
                        "dto_elems": nest_dto_elems,
                        "need_import_module": nest_dto_import_module,
                    }
                    CodeGenerator.gen_code(nest_dto_content, target)

                # 二层嵌套
                if lv2_need_create_nest_dto and not CommonUtil.is_empty(lv2_nest_dto_fp):
                    lv2_nest_dto_content = {
                        "sheet_name": lv2_nest_dto_filename,
                        "dto_elems": lv2_nest_dto_elems,
                        "need_import_module": lv2_nest_dto_import_module,
                    }
                    CodeGenerator.gen_code(lv2_nest_dto_content, target)

                if dto_num > 0:
                    content["need_import_module"] = need_import_module
                    protocol_data.append(content)

                index += 1

            return protocol_data
        else:
            logger.error("protocol_file=%s not exist" % protocol_file)
            print "protocol_file=%s not exist" % protocol_file
            return []

    @staticmethod
    def gen_copyright(fp):
        """
        生成版权信息
        :param fp:
        """
        FileWriter.writeline_with_endl(fp, CodeTemplate.java_template.get("copy_right"))

    @staticmethod
    def gen_import(fp, modules):
        """
        import模块
        :param modules: 需要import的模块列表
        :param fp:
        """
        for module in modules:
            if module == "list":
                text = "import java.util.List;"
            elif module == "date":
                text = "import java.util.Date;"
            elif module == "big_decimal":
                text = "import java.math.BigDecimal;"

            FileWriter.writeline_with_endl(fp, text)

        for import_elem in CodeTemplate.java_template.get("default_import_list"):
            text = "import " + import_elem + ";"
            FileWriter.writeline_with_endl(fp, text)

        if CodeTemplate.java_template.get("option_json_property"):
            for module in CodeTemplate.import_json_property:
                text = "import " + module + ";"
                FileWriter.writeline_with_endl(fp, text)

        if CodeTemplate.java_template.get("option_json_serialize"):
            for module in CodeTemplate.import_json_serialize:
                text = "import " + module + ";"
                FileWriter.writeline_with_endl(fp, text)

    @staticmethod
    def gen_package_name(fp):
        """
        生成包名
        :param fp:
        """
        FileWriter.writeline_with_endl(fp, CodeTemplate.java_template.get("package_name"))

    @staticmethod
    def class_define_begin(fp, classname):
        """
        类开始
        :param fp:
        :param classname:
        """
        text = CodeTemplate.java_template.get("class_definition") % classname
        FileWriter.writeline_with_endl(fp, text)

    @staticmethod
    def class_define_end(fp):
        """
        类结束
        :param fp:
        """
        text = CodeTemplate.java_template.get("class_definition_end")
        FileWriter.writeline_with_endl(fp, text)

    @staticmethod
    def property_define(fp, type_name, field_name):
        """
        定义属性
        :param fp:
        :param type_name:
        :param field_name:
        """
        text = CodeTemplate.java_template.get("property_definition") % (type_name, field_name)
        FileWriter.writeline_with_endl(fp, text)

    @staticmethod
    def property_comment(fp, content=""):
        """
        定义注释
        :param content: 注释内容
        :param fp: 文件对象
        """
        if CodeTemplate.java_template.get("option_comment"):
            text = CodeTemplate.java_template.get("property_comment") % content
            FileWriter.writeline_with_endl(fp, text, 1)

    @staticmethod
    def function_define_set(fp, type_name, field_name, field_name_cap):
        """
        定义set函数
        :param fp:
        :param type_name:
        :param field_name:
        :param field_name_cap:
        """
        text = CodeTemplate.java_template.get("function_definition_set") % (field_name_cap, type_name, field_name,
                                                                            field_name, field_name)
        FileWriter.writeline_with_endl(fp, text)

    @staticmethod
    def function_define_get(fp, type_name, field_name, field_name_cap):
        """
        定义get函数
        :param fp:
        :param type_name:
        :param field_name:
        :param field_name_cap:
        """
        text = CodeTemplate.java_template.get("function_definition_get") % (type_name, field_name_cap, field_name)
        FileWriter.writeline_with_endl(fp, text)

    @staticmethod
    def function_comment(fp, param="", param_desc=""):
        """
        函数注释
        :param param_desc: 参数描述
        :param param: 参数
        :param fp:
        """
        if CodeTemplate.java_template.get("option_comment"):
            text = CodeTemplate.java_template.get("function_comment") % (param, param_desc)
            FileWriter.writeline_with_endl(fp, text, 1)

    @staticmethod
    def json_property(fp, field_name):
        """
        生成json property注解
        :param fp:
        :param field_name:
        """
        if CodeTemplate.java_template.get("option_json_property"):
            text = CodeTemplate.java_template.get("json_property") % field_name
            FileWriter.writeline_with_endl(fp, text, 1)

    @staticmethod
    def json_deserialize(fp):
        """
        生成反序列化注解
        :param fp:
        """
        if CodeTemplate.java_template.get("option_json_serialize"):
            text = CodeTemplate.java_template.get("json_deserialize")
            FileWriter.writeline_with_endl(fp, text, 1)

    @staticmethod
    def json_serialize(fp):
        """
        生成序列化注解
        :param fp:
        """
        if CodeTemplate.java_template.get("option_json_serialize"):
            text = CodeTemplate.java_template.get("json_serialize")
            FileWriter.writeline_with_endl(fp, text, 1)

    @staticmethod
    def gen_body(fp, sheet):
        """
        生成代码主体
        :param sheet:
        :param fp:
        """
        sheet_name = sheet.get("sheet_name")
        dto_elems = sheet.get("dto_elems")

        if dto_elems is not None and sheet_name is not None:
            classname = sheet_name
            CodeGenerator.class_define_begin(fp, classname)

            for elem in dto_elems:
                elem_type = TypeDict.type_dict.get(elem.get("type").lower())
                if elem_type is None:
                    logger.error("Unknown or miss field type, elem=%s" % str(elem))
                    continue

                elem_field_name = CamelTransformTool.trans_underline_field_to_camel_field(elem.get("name"))
                if elem_field_name is None:
                    logger.error("miss field_name, elem=%s" % str(elem))
                    continue

                # 定义属性
                elem_property_comment = elem.get("comment")
                CodeGenerator.property_comment(fp, elem_property_comment)
                # 在属性上添加注解, 默认的注解方式
                if CodeTemplate.java_template.get("style_json_property") == Constant.json_property_style.get(
                        "above_property"):
                    CodeGenerator.json_property(fp, elem.get("name"))

                CodeGenerator.property_define(fp, elem_type, elem_field_name)

            for elem in dto_elems:
                elem_type = TypeDict.type_dict.get(elem.get("type").lower())
                elem_field_name = CamelTransformTool.trans_underline_field_to_camel_field(elem.get("name"))
                elem_field_name_cap = CamelTransformTool.trans_underline_field_to_camel_classname(elem.get("name"))
                if elem_type is None or elem_field_name is None:
                    continue

                # 定义set函数
                elem_property_comment = elem.get("comment")
                CodeGenerator.function_comment(fp, elem_field_name, elem_property_comment)

                if CodeTemplate.java_template.get("style_json_property") == Constant.json_property_style.get(
                        "above_function_set_upper_case"):
                    CodeGenerator.json_property(fp, elem.get("name"))

                if CodeTemplate.java_template.get("style_json_property") == Constant.json_property_style.get(
                        "above_function_set_lower_case"):
                    CodeGenerator.json_property(fp, elem_field_name)

                CodeGenerator.json_serialize(fp)
                CodeGenerator.function_define_set(fp, elem_type, elem_field_name, elem_field_name_cap)

                # 定义get函数
                CodeGenerator.function_comment(fp)
                if CodeTemplate.java_template.get("style_json_property") == Constant.json_property_style.get(
                        "above_function_set_upper_case"):
                    CodeGenerator.json_property(fp, elem_field_name)

                if CodeTemplate.java_template.get("style_json_property") == Constant.json_property_style.get(
                        "above_function_set_lower_case"):
                    CodeGenerator.json_property(fp, elem.get("name"))

                CodeGenerator.json_serialize(fp)
                CodeGenerator.function_define_get(fp, elem_type, elem_field_name, elem_field_name_cap)

            CodeGenerator.class_define_end(fp)

    @staticmethod
    def setRequestPropertyStyle(target):
        """
        设置请求的json property样式
        :param target: 生成的文件给target用, 与业务强相关，非通用逻辑
        """
        if target == Target.Target_openapi:
            CodeGenerator.set_option_json_property(False)  # openapi 不需要json property
        elif target == Target.Target_pmbank:
            CodeGenerator.set_option_json_property(True)
            CodeGenerator.set_json_property_style(Constant.json_property_style.get("above_function_set_lower_case"))
        elif target == Target.Target_normal:
            CodeGenerator.set_option_json_property(True)
            CodeGenerator.set_json_property_style(Constant.json_property_style.get("above_property"))
        else:
            CodeGenerator.set_option_json_property(False)

    @staticmethod
    def setResponsePropertyStyle(target):
        """
        设置响应的json property样式
        :param target: 生成的文件给target用, 与业务强相关，非通用逻辑
        """
        if target == Target.Target_openapi:
            CodeGenerator.set_option_json_property(False)  # openapi 不需要json property
        elif target == Target.Target_pmbank:
            CodeGenerator.set_option_json_property(True)
            CodeGenerator.set_json_property_style(Constant.json_property_style.get("above_function_set_upper_case"))
        elif target == Target.Target_normal:
            CodeGenerator.set_option_json_property(True)
            CodeGenerator.set_json_property_style(Constant.json_property_style.get("above_property"))
        else:
            CodeGenerator.set_option_json_property(False)

    # 以下接口提供给用户使用,
    # 通过代码覆盖配置文件, 而不是直接到配置文件中修改
    @staticmethod
    def set_package_name(package):
        """
        设置生成代码的完整包名
        :param package: 例如: com.xxx.yyy
        """
        CodeTemplate.java_template["package_name"] = "package " + package + ";"

    @staticmethod
    def set_protocol_file(pf):
        """
        设置协议文件
        :param file: 需包含完整路径名
        """
        CodeTemplate.java_template["protocol_file"] = pf

    @staticmethod
    def set_option_json_property(option):
        """
        是否生成json property注解
        :param option: true or false
        """
        CodeTemplate.java_template["option_json_property"] = option

    @staticmethod
    def set_option_json_serialize(option):
        """
        是否生成序列化注解
        :param option:
        """
        CodeTemplate.java_template["option_json_serialize"] = option

    @staticmethod
    def set_option_comment(option):
        """
        是否生成注释
        :param option:
        """
        CodeTemplate.java_template["option_comment"] = option

    @staticmethod
    def extend_import_module(modules):
        """
        添加需要导入的模块, 会追加到默认导入的模块列表中, 会去重
        :param modules: 列表
        """
        current_import_list = CodeTemplate.java_template.get("default_import_list")

        for module in modules:
            if module in current_import_list:
                modules.remove(module)

        current_import_list.extend(modules)

    @staticmethod
    def set_import_module(modules):
        """
        设置默认加载的模块列表
        例如:
        :param modules:
        :return:
        """
        CodeTemplate.java_template["default_import_list"] = modules

    @staticmethod
    def set_json_property_style(style_type):
        """
        设置json property方式
        :param style_type: json property 1-get和set使用相同的字段名 2-使用excel中的字段名
        """
        CodeTemplate.java_template["style_json_property"] = style_type

    @staticmethod
    def set_service_name(name):
        """
        服务名，决定了dto的输出目录
        :param name:
        """
        CodeGenerator.service_name = name


"""
仅用于自测
"""
if __name__ == "__main__":
    logger.debug("gen start")
    # package_name = raw_input("Please input java package name(like com.xxx.xxx):")
    package_name = "com.test"
    CodeGenerator.set_package_name(package_name)

    CodeGenerator.set_option_comment(True)
    CodeGenerator.set_option_json_serialize(False)

    module_list = [
        # "com.xxx.test",
    ]
    CodeGenerator.extend_import_module(module_list)
    CodeGenerator.set_protocol_file("D:\docs\protocol_v2_0217.xls")
    CodeGenerator.set_service_name("wexxxx")

    start_time = time.clock()
    CodeGenerator.run(Target.Target_normal)
    # CodeGenerator.run(Target.Target_openapi)
    # CodeGenerator.run(Target.Target_pmbank)
    stop_time = time.clock()
    use_time = stop_time - start_time

    logger.debug("gen success. Time spend:%.4f(s)" % use_time)
    print "gen success. Time spend:%.4f(s)" % use_time
