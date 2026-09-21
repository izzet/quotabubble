import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {BubbleRenderer} from './renderer.js';

const BUS_NAME = 'dev.izzet.quotabubble';
const OBJECT_PATH = '/dev/izzet/quotabubble';
const INTERFACE_NAME = 'dev.izzet.quotabubble.Service1';
const DRAG_THRESHOLD = 4;

export default class QuotaBubbleExtension extends Extension {
    enable() {
        this._enabled = true;
        this._expanded = false;
        this._renderer = new BubbleRenderer();
        this._actor = this._renderer.actor;
        this._menu = new PopupMenu.PopupMenu(this._actor, 0.5, St.Side.TOP);
        this._menu.addAction('Refresh', () => this._requestRefresh());
        this._menu.addAction('Settings…', () => this._openSettings());
        Main.uiGroup.add_child(this._menu.actor);
        this._menu.actor.hide();
        this._buttonPressId = this._actor.connect(
            'button-press-event',
            (_actor, event) => this._beginPointerAction(event),
        );
        Main.layoutManager.addChrome(this._actor, {
            affectsStruts: false,
            trackFullscreen: false,
        });
        this._actor.set_position(24, 24);
        this._nameWatchId = Gio.bus_watch_name(
            Gio.BusType.SESSION,
            BUS_NAME,
            Gio.BusNameWatcherFlags.NONE,
            () => this._connectService(),
            () => this._serviceVanished(),
        );
    }

    disable() {
        this._enabled = false;
        this._endPointerAction();
        if (this._nameWatchId)
            Gio.bus_unwatch_name(this._nameWatchId);
        this._nameWatchId = null;
        this._disconnectService();
        this._menu?.destroy();
        this._menu = null;
        this._actor?.disconnect(this._buttonPressId);
        this._actor?.destroy();
        this._actor = null;
    }

    async _connectService() {
        this._disconnectService();
        try {
            const proxy = await this._createProxy();
            if (!this._enabled)
                return;
            this._proxy = proxy;
            this._signalId = proxy.connectSignal(
                'StateChanged',
                (_proxy, _sender, _name, parameters) => this._render(parameters.deepUnpack()[0]),
            );
            const result = await this._getState(proxy);
            if (this._enabled)
                this._render(result.deepUnpack()[0]);
        } catch (error) {
            console.error(`QuotaBubble could not connect to its service: ${error.message}`);
            this._renderFallback('Service unavailable');
        }
    }

    _disconnectService() {
        if (this._signalId !== undefined)
            this._proxy?.disconnectSignal(this._signalId);
        this._signalId = undefined;
        this._proxy = null;
    }

    _serviceVanished() {
        this._disconnectService();
        if (this._enabled)
            this._renderFallback('Service unavailable');
    }

    _createProxy() {
        return new Promise((resolve, reject) => {
            Gio.DBusProxy.new_for_bus(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                null,
                BUS_NAME,
                OBJECT_PATH,
                INTERFACE_NAME,
                null,
                (_source, result) => {
                    try {
                        resolve(Gio.DBusProxy.new_for_bus_finish(result));
                    } catch (error) {
                        reject(error);
                    }
                },
            );
        });
    }

    _getState(proxy) {
        return new Promise((resolve, reject) => {
            proxy.call(
                'GetState',
                null,
                Gio.DBusCallFlags.NONE,
                -1,
                null,
                (_proxy, result) => {
                    try {
                        resolve(proxy.call_finish(result));
                    } catch (error) {
                        reject(error);
                    }
                },
            );
        });
    }

    _beginPointerAction(event) {
        if (event.get_button() === Clutter.BUTTON_SECONDARY) {
            this._menu.open();
            return Clutter.EVENT_STOP;
        }
        if (event.get_button() !== Clutter.BUTTON_PRIMARY)
            return Clutter.EVENT_PROPAGATE;

        const [x, y] = event.get_coords();
        this._pointerAction = {
            x,
            y,
            actorX: this._actor.x,
            actorY: this._actor.y,
            dragged: false,
        };
        this._stageEventId = global.stage.connect(
            'captured-event',
            (_stage, capturedEvent) => this._handleCapturedEvent(capturedEvent),
        );
        return Clutter.EVENT_STOP;
    }

    _handleCapturedEvent(event) {
        if (!this._pointerAction)
            return Clutter.EVENT_PROPAGATE;

        if (event.type() === Clutter.EventType.MOTION) {
            const [x, y] = event.get_coords();
            const dx = x - this._pointerAction.x;
            const dy = y - this._pointerAction.y;
            if (Math.abs(dx) >= DRAG_THRESHOLD || Math.abs(dy) >= DRAG_THRESHOLD)
                this._pointerAction.dragged = true;
            if (this._pointerAction.dragged)
                this._actor.set_position(this._pointerAction.actorX + dx, this._pointerAction.actorY + dy);
            return Clutter.EVENT_STOP;
        }

        if (event.type() === Clutter.EventType.BUTTON_RELEASE) {
            const dragged = this._pointerAction.dragged;
            this._endPointerAction();
            if (!dragged)
                this._setExpanded(!this._expanded);
            return Clutter.EVENT_STOP;
        }

        return Clutter.EVENT_PROPAGATE;
    }

    _endPointerAction() {
        if (this._stageEventId) {
            global.stage.disconnect(this._stageEventId);
            this._stageEventId = null;
        }
        this._pointerAction = null;
    }

    _setExpanded(expanded) {
        this._expanded = expanded;
        this._renderer?.setExpanded(expanded);
    }

    _render(payload) {
        try {
            const state = JSON.parse(payload);
            if (state.version !== 1 || !Array.isArray(state.providers))
                throw new Error('unsupported presentation contract');
            this._renderer?.setView(state);
        } catch (error) {
            console.error(`QuotaBubble received an invalid service state: ${error.message}`);
            this._renderFallback('Invalid service data');
        }
    }

    _renderFallback(message) {
        this._renderer?.setView({
            version: 1,
            providers: [{
                name: 'QuotaBubble',
                stale: false,
                compact_metrics: [{label: message, detail: message}],
                expanded_metrics: [{label: message, detail: message}],
            }],
        });
    }

    _requestRefresh() {
        this._proxy?.call(
            'Refresh',
            null,
            Gio.DBusCallFlags.NONE,
            -1,
            null,
            (_proxy, result) => {
                try {
                    this._proxy?.call_finish(result);
                } catch (error) {
                    console.error(`QuotaBubble could not refresh: ${error.message}`);
                }
            },
        );
    }

    _openSettings() {
        const application = Gio.DesktopAppInfo.new('dev.izzet.QuotaBubbleSettings.desktop');
        if (application)
            application.launch([], null);
        else
            console.error('QuotaBubble settings application is not installed');
    }
}
