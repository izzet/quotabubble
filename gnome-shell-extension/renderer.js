import Cairo from 'cairo';
import St from 'gi://St';

import {TOKENS} from './generated/tokens.js';

const {color, size} = TOKENS;

function rgba(hex) {
    const value = hex.slice(1);
    const alpha = value.length === 8 ? parseInt(value.slice(6, 8), 16) / 255 : 1;
    return [
        parseInt(value.slice(0, 2), 16) / 255,
        parseInt(value.slice(2, 4), 16) / 255,
        parseInt(value.slice(4, 6), 16) / 255,
        alpha,
    ];
}

function setColor(cr, value) {
    cr.setSourceRGBA(...rgba(value));
}

function roundedRect(cr, x, y, width, height, radius) {
    const r = Math.min(radius, width / 2, height / 2);
    cr.newSubPath();
    cr.arc(x + width - r, y + r, r, -Math.PI / 2, 0);
    cr.arc(x + width - r, y + height - r, r, 0, Math.PI / 2);
    cr.arc(x + r, y + height - r, r, Math.PI / 2, Math.PI);
    cr.arc(x + r, y + r, r, Math.PI, Math.PI * 1.5);
    cr.closePath();
}

function text(cr, value, x, y, options = {}) {
    const {align = 'left', bold = false, color: textColor = color.text} = options;
    cr.selectFontFace('Sans', Cairo.FontSlant.NORMAL,
        bold ? Cairo.FontWeight.BOLD : Cairo.FontWeight.NORMAL);
    cr.setFontSize(11);
    setColor(cr, textColor);
    const width = cr.textExtents(value).width;
    const drawX = align === 'right' ? x - width : x;
    cr.moveTo(drawX, y);
    cr.showText(value);
}

function textWidth(value) {
    const surface = new Cairo.ImageSurface(Cairo.Format.ARGB32, 1, 1);
    const cr = new Cairo.Context(surface);
    cr.selectFontFace('Sans', Cairo.FontSlant.NORMAL, Cairo.FontWeight.NORMAL);
    cr.setFontSize(11);
    const width = cr.textExtents(value).xAdvance;
    cr.$dispose();
    return width;
}

export class BubbleRenderer {
    constructor() {
        this.actor = new St.DrawingArea({
            style_class: 'quotabubble',
            reactive: true,
            track_hover: true,
        });
        this._view = {providers: []};
        this._expanded = false;
        this.actor.connect('repaint', area => this._paint(area));
        this._resize();
    }

    setView(view) {
        this._view = view;
        this._resize();
        this.actor.queue_repaint();
    }

    setExpanded(expanded) {
        this._expanded = expanded;
        this._resize();
        this.actor.queue_repaint();
    }

    _resize() {
        const providers = this._view.providers;
        const contentHeight = this._expanded
            ? this._expandedContentHeight(providers)
            : Math.max(1, providers.length) * size.compactRowHeight;
        const compactWidth = this._compactWidth(providers);
        this.actor.set_size(
            this._expanded ? Math.max(size.expandedWidth, compactWidth) : compactWidth,
            size.padding * 2 + contentHeight,
        );
    }

    _compactWidth(providers) {
        const widestName = Math.max(0, ...providers.map(provider => textWidth(provider.name)));
        const groups = 2 * this._miniGroupWidth() + size.compactGroupGap;
        return Math.max(size.compactWidth, size.padding * 2 + widestName + size.nameGap + groups);
    }

    _expandedContentHeight(providers) {
        return providers.reduce((height, provider, index) => height
            + size.headerRowHeight
            + provider.expanded_metrics.length * size.metricRowHeight
            + (index < providers.length - 1 ? size.providerGap : 0), 0);
    }

    _paint(area) {
        const cr = area.get_context();
        const [width, height] = area.get_surface_size();
        roundedRect(cr, 0.5, 0.5, width - 1, height - 1, size.radius);
        setColor(cr, color.surface);
        cr.fillPreserve();
        cr.setLineWidth(1);
        setColor(cr, color.border);
        cr.stroke();

        if (this._view.providers.length === 0) {
            text(cr, 'No providers', width / 2, height / 2 + 4, {align: 'right', color: color.textDim});
        } else if (this._expanded) {
            this._paintExpanded(cr, width);
        } else {
            this._paintCompact(cr, width);
        }
        cr.$dispose();
    }

    _paintCompact(cr, width) {
        let y = size.padding;
        for (const provider of this._view.providers) {
            const baseline = y + 17;
            text(cr, provider.name, size.padding, baseline, {
                color: provider.stale ? color.textDim : color.text,
            });
            const metrics = provider.compact_metrics;
            const secondRight = width - size.padding;
            const firstRight = secondRight - this._miniGroupWidth() - size.compactGroupGap;
            if (metrics.length > 0 && Number.isInteger(metrics[0].percent))
                this._paintMini(cr, metrics[0], firstRight, y, provider.stale);
            if (metrics.length > 1 && Number.isInteger(metrics[1].percent))
                this._paintMini(cr, metrics[1], secondRight, y, provider.stale);
            else if (metrics.length > 0 && metrics[0].percent === null)
                text(cr, metrics[0].detail ?? metrics[0].label, width - size.padding, baseline, {
                    align: 'right', color: metrics[0].detail != null ? color.text : color.textDim,
                });
            y += size.compactRowHeight;
        }
    }

    _miniGroupWidth() {
        return size.miniLabelWidth + size.miniGap + size.miniBarWidth
            + size.miniGap + size.miniPercentWidth;
    }

    _paintMini(cr, metric, right, top, stale) {
        const percent = `${metric.percent}%`;
        const left = right - this._miniGroupWidth();
        text(cr, metric.compact_label ?? metric.label, left + size.miniLabelWidth, top + 17, {align: 'right', color: color.textDim});
        const barLeft = left + size.miniLabelWidth + size.miniGap;
        roundedRect(cr, barLeft, top + 10, size.miniBarWidth, size.barHeight, 3);
        setColor(cr, color.track);
        cr.fill();
        if (metric.bar_fraction > 0) {
            roundedRect(cr, barLeft, top + 10, size.miniBarWidth * metric.bar_fraction, size.barHeight, 3);
            setColor(cr, color[metric.tone]);
            cr.fill();
        }
        text(cr, percent, right, top + 17, {align: 'right', color: stale ? color.textDim : color.text});
    }

    _paintExpanded(cr, width) {
        let y = size.padding;
        for (const provider of this._view.providers) {
            const headerBaseline = y + 15;
            text(cr, provider.name, size.padding, headerBaseline, {
                bold: true, color: provider.stale ? color.textDim : color.text,
            });
            if (provider.trailing)
                text(cr, provider.trailing, width - size.padding, headerBaseline, {align: 'right', color: color.textDim});
            y += size.headerRowHeight;
            for (const metric of provider.expanded_metrics) {
                this._paintMetric(cr, metric, y, width);
                y += size.metricRowHeight;
            }
            y += size.providerGap;
        }
    }

    _paintMetric(cr, metric, top, width) {
        const baseline = top + 16;
        if (!Number.isInteger(metric.percent)) {
            text(cr, metric.label, size.padding, baseline, {
                color: metric.detail != null ? color.text : color.textDim,
            });
            if (metric.detail != null)
                text(cr, metric.detail, size.padding + size.metricLabelWidth, baseline, {color: color.textDim});
            return;
        }
        text(cr, metric.label, size.padding, baseline, {color: color.text});
        const barLeft = size.padding + size.metricLabelWidth;
        roundedRect(cr, barLeft, top + 8, size.metricBarWidth, size.barHeight, 3);
        setColor(cr, color.track);
        cr.fill();
        if (metric.bar_fraction > 0) {
            roundedRect(cr, barLeft, top + 8, size.metricBarWidth * metric.bar_fraction, size.barHeight, 3);
            setColor(cr, color[metric.tone]);
            cr.fill();
        }
        text(cr, `${metric.percent}%`, barLeft + size.metricBarWidth + size.metricPercentWidth, baseline, {align: 'right'});
        if (metric.reset_text)
            text(cr, metric.reset_text, width - size.padding, baseline, {align: 'right', color: color.textDim});
    }
}
