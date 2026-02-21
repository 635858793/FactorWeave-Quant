#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步工作线程模块
"""

# 延迟导入，避免在模块级别导入时卡住
_AsyncDataSignals = None
_AsyncDataWorker = None
_AsyncStrategyWorker = None
_AlertHistorySignals = None
_AlertHistoryWorker = None
_TabLoadSignals = None
_TabLoadWorker = None
_NotificationTestSignals = None
_EmailTestWorker = None
_SMSTestWorker = None

def _import_async_workers():
    """延迟导入async_workers模块"""
    global _AsyncDataSignals, _AsyncDataWorker, _AsyncStrategyWorker
    global _AlertHistorySignals, _AlertHistoryWorker
    global _TabLoadSignals, _TabLoadWorker, _NotificationTestSignals
    global _EmailTestWorker, _SMSTestWorker
    
    if _AsyncDataSignals is None:
        from .async_workers import (
            AsyncDataSignals,
            AsyncDataWorker,
            AsyncStrategyWorker,
            AlertHistorySignals,
            AlertHistoryWorker,
            TabLoadSignals,
            TabLoadWorker,
            NotificationTestSignals,
            EmailTestWorker,
            SMSTestWorker
        )
        _AsyncDataSignals = AsyncDataSignals
        _AsyncDataWorker = AsyncDataWorker
        _AsyncStrategyWorker = AsyncStrategyWorker
        _AlertHistorySignals = AlertHistorySignals
        _AlertHistoryWorker = AlertHistoryWorker
        _TabLoadSignals = TabLoadSignals
        _TabLoadWorker = TabLoadWorker
        _NotificationTestSignals = NotificationTestSignals
        _EmailTestWorker = EmailTestWorker
        _SMSTestWorker = SMSTestWorker

def get_AsyncDataSignals(*args, **kwargs):
    """延迟导入AsyncDataSignals"""
    _import_async_workers()
    return _AsyncDataSignals(*args, **kwargs)

def get_AsyncDataWorker(*args, **kwargs):
    """延迟导入AsyncDataWorker"""
    _import_async_workers()
    return _AsyncDataWorker(*args, **kwargs)

def get_AsyncStrategyWorker(*args, **kwargs):
    """延迟导入AsyncStrategyWorker"""
    _import_async_workers()
    return _AsyncStrategyWorker(*args, **kwargs)

def get_AlertHistorySignals(*args, **kwargs):
    """延迟导入AlertHistorySignals"""
    _import_async_workers()
    return _AlertHistorySignals(*args, **kwargs)

def get_AlertHistoryWorker(*args, **kwargs):
    """延迟导入AlertHistoryWorker"""
    _import_async_workers()
    return _AlertHistoryWorker(*args, **kwargs)

def get_TabLoadSignals(*args, **kwargs):
    """延迟导入TabLoadSignals"""
    _import_async_workers()
    return _TabLoadSignals(*args, **kwargs)

def get_TabLoadWorker(*args, **kwargs):
    """延迟导入TabLoadWorker"""
    _import_async_workers()
    return _TabLoadWorker(*args, **kwargs)

def get_NotificationTestSignals(*args, **kwargs):
    """延迟导入NotificationTestSignals"""
    _import_async_workers()
    return _NotificationTestSignals(*args, **kwargs)

def get_EmailTestWorker(*args, **kwargs):
    """延迟导入EmailTestWorker"""
    _import_async_workers()
    return _EmailTestWorker(*args, **kwargs)

def get_SMSTestWorker(*args, **kwargs):
    """延迟导入SMSTestWorker"""
    _import_async_workers()
    return _SMSTestWorker(*args, **kwargs)

# 为了兼容性，保留原有的类名
AsyncDataSignals = get_AsyncDataSignals
AsyncDataWorker = get_AsyncDataWorker
AsyncStrategyWorker = get_AsyncStrategyWorker
AlertHistorySignals = get_AlertHistorySignals
AlertHistoryWorker = get_AlertHistoryWorker
TabLoadSignals = get_TabLoadSignals
TabLoadWorker = get_TabLoadWorker
NotificationTestSignals = get_NotificationTestSignals
EmailTestWorker = get_EmailTestWorker
SMSTestWorker = get_SMSTestWorker

__all__ = [
    'AsyncDataSignals',
    'AsyncDataWorker',
    'AsyncStrategyWorker',
    'AlertHistorySignals',
    'AlertHistoryWorker',
    'TabLoadSignals',
    'TabLoadWorker',
    'NotificationTestSignals',
    'EmailTestWorker',
    'SMSTestWorker'
]