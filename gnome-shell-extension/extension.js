import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const BUS_NAME = 'dev.izzet.quotabubble';
const OBJECT_PATH = '/dev/izzet/quotabubble';
const INTERFACE_NAME = 'dev.izzet.quotabubble.Service1';
const DRAG_THRESHOLD = 4;

export default class QuotaBubbleExtension extends Extension {
    enable() {
        this._enabled = true;
        this._expanded = false;
        this._actor = new St.BoxLayout({
            style_class: 'quotabubble',
            vertical: true,
            reactive: true,
            track_hover: true,
        });
        this._summary = new St.Label({
            style_class: 'quotabubble-summary',
            text: 'QuotaBubble  ·  Loading…',
        });
        this._details = new St.BoxLayout({
            style_class: 'quotabubble-details',
            vertical: true,
        });
        this._actor.add_child(this._summary);
        this._actor.add_child(this._details);
        this._details.hide();
        this._buttonPressId = this._actor.connect(
            'button-press-event',
            (_actor, event) => this._beginPointerAction(event),
        );
        Main.layoutManager.addChrome(this._actor, {
            affectsStruts: false,
            trackFullscreen: false,
        });
        this._actor.set_position(24, 24);
        this._connectService();
    }

    disable() {
        this._enabled = false;
        this._endPointerAction();
        if (this._signalId !== undefined)
            this._proxy?.disconnectSignal(this._signalId);
        this._signalId = undefined;
        this._proxy = null;
        this._actor?.disconnect(this._buttonPressId);
        this._actor?.destroy();
        this._actor = null;
    }

    async _connectService() {
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
            this._summary?.set_text('QuotaBubble  ·  Service unavailable');
        }
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
        if (expanded)
            this._details.show();
        else
            this._details.hide();
    }

    _render(payload) {
        try {
            const state = JSON.parse(payload);
            const rows = state.snapshots.map(snapshot => this._snapshotText(snapshot));
            this._summary?.set_text(rows.length ? rows.join('  ·  ') : 'QuotaBubble  ·  No providers');
            this._details?.destroy_all_children();
            for (const row of rows)
                this._details?.add_child(new St.Label({style_class: 'quotabubble-row', text: row}));
        } catch (error) {
            console.error(`QuotaBubble received an invalid service state: ${error.message}`);
            this._summary?.set_text('QuotaBubble  ·  Invalid service data');
        }
    }

    _snapshotText(snapshot) {
        if (snapshot.status !== 'ok')
            return `${snapshot.display_name}  ${snapshot.message ?? snapshot.status}`;
        const windows = snapshot.windows.map(window => `${window.label} ${Math.round(window.used_pct)}%`);
        return windows.length ? `${snapshot.display_name}  ${windows.join('  ·  ')}` : snapshot.display_name;
    }
}
