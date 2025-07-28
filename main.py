import sys
import json
import random
from decimal import Decimal
from PySide6 import QtWidgets, QtCore, QtGui
import rectpack
from qt_material import apply_stylesheet


class PannableGraphicsView(QtWidgets.QGraphicsView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._panning = False
        self._start_pos = QtCore.QPoint()
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        self.setMouseTracking(True)
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._panning = True
            self._start_pos = event.position().toPoint()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position().toPoint() - self._start_pos
            self._start_pos = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._panning = False
            self.setCursor(QtCore.Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        self.scale(zoom_factor, zoom_factor)


class PackingViewer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Container Packing Visualiser - 2D")
        self.setWindowIcon(QtGui.QIcon("N:/Development/container_packing/icon.png"))
        self.resize(1280, 720)

        self._create_menu_bar()

        self._save_name = None

        # --- Left Sidebar Content ---
        sidebar_widget = QtWidgets.QWidget()
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar_widget)

        # Container Section
        sidebar_layout.addWidget(QtWidgets.QLabel("Container Dimensions"))
        self.container_table = self._create_container_table()
        sidebar_layout.addWidget(self.container_table)

        sidebar_layout.addSpacing(20)

        # Load Section
        load_section = QtWidgets.QWidget()
        load_section_layout = QtWidgets.QVBoxLayout(load_section)
        load_section_layout.setContentsMargins(0, 0, 0, 0)
        load_section_layout.setSpacing(5)

        load_section_layout.addWidget(QtWidgets.QLabel("Load Item Dimensions"))
        self.load_table = self._create_load_table()
        self.load_table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        load_section_layout.addWidget(self.load_table)

        v_header = self.load_table.verticalHeader()
        v_header.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        v_header.customContextMenuRequested.connect(self._on_vertical_header_right_click)

        self.add_load_btn = QtWidgets.QPushButton("Add Load")
        self.add_load_btn.clicked.connect(self._add_load_row)
        load_section_layout.addWidget(self.add_load_btn)

        load_section.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sidebar_layout.addWidget(load_section)

        self.run_btn = QtWidgets.QPushButton("Run Packing Simulation")
        self.run_btn.clicked.connect(self.run_packing)
        sidebar_layout.addWidget(self.run_btn)

        # --- Canvas (2D View) ---
        self.canvas = PannableGraphicsView()
        self.scene = QtWidgets.QGraphicsScene()
        # self.scene.setSceneRect(-1000, -1000, 1000, 1000)  # Width x Height in scene coordinates
        self.canvas.setScene(self.scene)
        
        # Set darker background
        self.canvas.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(20, 45, 45)))
        self.scene.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(20, 45, 45)))

        # --- Splitter and Main Layout ---
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_splitter.addWidget(sidebar_widget)
        main_splitter.addWidget(self.canvas)
        main_splitter.setSizes([int(self.width() * 0.35), int(self.width() * 0.65)])

        central_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QHBoxLayout(central_widget)
        main_layout.addWidget(main_splitter)
         
        self.setCentralWidget(central_widget)

        self.load_row_colours = {}
        self._initialize_default_data()
        self.run_packing(display_msg=False)

    def _on_vertical_header_right_click(self, pos):
        header = self.load_table.verticalHeader()
        row = header.logicalIndexAt(pos)

        if row == -1:
            return

        menu = QtWidgets.QMenu(self)
        delete_action = menu.addAction("Delete Item")
        action = menu.exec_(header.mapToGlobal(pos))

        if action == delete_action:
            self.load_table.removeRow(row)

    def _create_menu_bar(self):
        self.menu_bar = self.menuBar()
        file_menu = self.menu_bar.addMenu("&File")
        help_menu = self.menu_bar.addMenu("&Help")

        new_action = QtGui.QAction("&New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)

        save_action = QtGui.QAction("&Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        save_as_action = QtGui.QAction("&Save As", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)

        load_action = QtGui.QAction("&Load", self)
        load_action.setShortcut("Ctrl+L")
        load_action.triggered.connect(self.load_file)
        file_menu.addAction(load_action)

        file_menu.addSeparator()
        
        zoom_fit_action = QtGui.QAction("Zoom to &Fit", self)
        zoom_fit_action.setShortcut("Ctrl+F")
        zoom_fit_action.triggered.connect(self._zoom_to_fit)
        file_menu.addAction(zoom_fit_action)

    def _create_container_table(self):
        table = QtWidgets.QTableWidget(1, 3)
        table.setHorizontalHeaderLabels(["Name", "W (m)", "L (m)"])
        table.setItem(0, 0, self._create_centered_table_item("20-foot container (TEU - Twenty-foot Equivalent Unit)"))
        table.setItem(0, 1, self._create_centered_table_item("2.44"))
        table.setItem(0, 2, self._create_centered_table_item("6.06"))
        table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        # Hide vertical header for container table
        table.verticalHeader().setVisible(False)

        # Set column resize modes and widths
        table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        table.setColumnWidth(1, 55)  # W
        table.setColumnWidth(2, 55)  # H

        table.setEditTriggers(QtWidgets.QAbstractItemView.AllEditTriggers)

        # Set maximum height for the container table
        header_height = table.horizontalHeader().height()
        row_height = table.rowHeight(0)
        calculated_height = header_height + row_height + 2
        table.setMaximumHeight(calculated_height)

        return table

    def _create_load_table(self):
        # Start with 0 rows, the first row will be added by _add_load_row_with_color
        table = QtWidgets.QTableWidget(0, 4)  # 4 columns: Name, W, H, Color
        table.setHorizontalHeaderLabels(["Name", "W (m)", "L (m)", "Color"])
        # Show vertical header for load table
        table.verticalHeader().setVisible(True)
        table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        table.setEditTriggers(QtWidgets.QAbstractItemView.AllEditTriggers)

        # Set column resize modes and widths
        table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
        table.setColumnWidth(1, 55)  # W
        table.setColumnWidth(2, 55)  # H
        table.setColumnWidth(3, 60)  # Color
        

        return table

    def _initialize_default_data(self):
        """Add initial load row with a default random color"""
        self._add_load_row_with_color(self.load_table, 0)

    def _create_centered_table_item(self, text):
        item = QtWidgets.QTableWidgetItem(text)
        item.setTextAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        return item

    def _add_load_row(self):
        row_count = self.load_table.rowCount()
        self._add_load_row_with_color(self.load_table, row_count)

    def _add_load_row_with_color(self, table, row_index, name=None, w=None, h=None, color_rgba=None):
        table.insertRow(row_index)

        # Fallback: copy width/height from the last existing row
        if w is None or h is None:
            if row_index > 0:
                prev_w_item = table.item(row_index - 1, 1)
                prev_h_item = table.item(row_index - 1, 2)
                if w is None and prev_w_item and prev_w_item.text().strip().isdigit():
                    w = int(prev_w_item.text().strip())
                if h is None and prev_h_item and prev_h_item.text().strip().isdigit():
                    h = int(prev_h_item.text().strip())

        # Final fallback if still None
        if w is None:
            w = "1.2"
        if h is None:
            h = "1.0"

        # Set name
        item_name = name if name is not None else f"Load {row_index + 1}"
        table.setItem(row_index, 0, self._create_centered_table_item(item_name))

        # Set dimensions
        table.setItem(row_index, 1, self._create_centered_table_item(str(w)))
        table.setItem(row_index, 2, self._create_centered_table_item(str(h)))

        color_button = QtWidgets.QPushButton()
        color_button.setFixedSize(32, 18)
        color_button.clicked.connect(lambda checked, row=row_index: self._on_color_button_clicked(row))

        # Create a QWidget wrapper with a horizontal layout
        container_widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container_widget)
        layout.addWidget(color_button)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)

        table.setCellWidget(row_index, 3, container_widget)

        # Set colour
        final_color_rgba = color_rgba if color_rgba is not None else self._generate_random_color()
        self._set_button_color(color_button, final_color_rgba)

        # Store colour for that row
        self.load_row_colours[row_index] = final_color_rgba


    def _generate_random_color(self):
        # Generate distinct, not too dark/light colors
        r = random.uniform(0.3, 0.9)
        g = random.uniform(0.3, 0.9)
        b = random.uniform(0.3, 0.9)
        return (r, g, b, 0.8)

    def _set_button_color(self, button, rgba_color):
        r, g, b, a = rgba_color
        # Convert float (0-1) to int (0-255) for stylesheet
        r_int, g_int, b_int, a_int = int(r * 255), int(g * 255), int(b * 255), int(a * 255)
        button.setStyleSheet(f"background-color: rgba({r_int}, {g_int}, {b_int}, {a_int}); border: 1px solid gray;")
        # Store the float rgba tuple as a property
        button.setProperty("item_color", rgba_color)

    def _on_color_button_clicked(self, row):
        current_color_rgba = self.load_row_colours.get(row)

        if current_color_rgba is None:
            return  # Or handle gracefully

        current_qcolor = QtGui.QColor(
            int(current_color_rgba[0] * 255),
            int(current_color_rgba[1] * 255),
            int(current_color_rgba[2] * 255),
            int(current_color_rgba[3] * 255)
        )

        new_qcolor = QtWidgets.QColorDialog.getColor(current_qcolor, self, "Select Colour")

        if new_qcolor.isValid():
            new_rgba = (
                new_qcolor.red() / 255,
                new_qcolor.green() / 255,
                new_qcolor.blue() / 255,
                new_qcolor.alpha() / 255
            )
            self.load_row_colours[row] = new_rgba

            button_container = self.load_table.cellWidget(row, 3)
            if button_container is not None:
                button = button_container.findChild(QtWidgets.QPushButton)
                if button is not None:
                    self._set_button_color(button, new_rgba)

    def new_file(self):
        # Clear container table
        self.container_table.clearContents()
        self.container_table.setRowCount(1)
        self.container_table.setItem(0, 0, self._create_centered_table_item("Container"))
        self.container_table.setItem(0, 1, self._create_centered_table_item("10"))
        self.container_table.setItem(0, 2, self._create_centered_table_item("10"))

        # Clear load table
        self.load_table.clearContents()
        self.load_table.setRowCount(0)
        self._add_load_row_with_color(self.load_table, 0)

        # Clear canvas
        self.scene.clear()

    def save_file(self):
        file_name = self._save_name
        if not file_name:
            file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Packing Data", "", "JSON Files (*.json);;All Files (*)")
        
        self.save_file_as(file_name=file_name)


    def save_file_as(self, *args, file_name=None):
        if file_name is None:
            file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Packing Data As", "", "JSON Files (*.json);;All Files (*)")

        if file_name:
            
            data = {
                "container": {},
                "loads": []
            }

            # Get container data
            container_row = 0
            data["container"]["name"] = self.container_table.item(container_row, 0).text()
            data["container"]["width"] = self.container_table.item(container_row, 1).text()
            data["container"]["height"] = self.container_table.item(container_row, 2).text()
            

            # Get loads data
            for row in range(self.load_table.rowCount()):
                load_data = {}
                load_data["name"] = self.load_table.item(row, 0).text() if self.load_table.item(row, 0) else ""
                load_data["width"] = self.load_table.item(row, 1).text() if self.load_table.item(row, 1) else "1"
                load_data["height"] = self.load_table.item(row, 2).text() if self.load_table.item(row, 2) else "1"
                button_container = self.load_table.cellWidget(row, 3)
                if button_container is not None:
                    color_button = button_container.findChild(QtWidgets.QPushButton)
                load_data["color"] = color_button.property("item_color") if color_button else (0.5, 0.5, 0.5, 0.8)
                data["loads"].append(load_data)

            try:
                with open(file_name, 'w') as f:
                    json.dump(data, f, indent=4)
                self._save_name = file_name
                QtWidgets.QMessageBox.information(self, "Save Successful", "Data saved successfully!")
            except IOError as e:
                QtWidgets.QMessageBox.warning(self, "Save Error", f"Could not save file: {e}")

    def load_file(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Packing Data", "", "JSON Files (*.json);;All Files (*)")
        if file_name:
            
            try:
                with open(file_name, 'r') as f:
                    data = json.load(f)

                # Load container data
                container_data = data.get("container", {})
                self.container_table.setItem(0, 0, self._create_centered_table_item(container_data.get("name", "Container")))
                self.container_table.setItem(0, 1, self._create_centered_table_item(container_data.get("width", "10")))
                self.container_table.setItem(0, 2, self._create_centered_table_item(container_data.get("height", "10")))

                # Load loads data
                self.load_table.clearContents()
                self.load_table.setRowCount(0)
                loads_data = data.get("loads", [])
                for i, load in enumerate(loads_data):
                    self._add_load_row_with_color(
                        self.load_table, i,
                        name=load.get("name"),
                        w=load.get("width"),
                        h=load.get("height"),
                        color_rgba=load.get("color")
                    )
                if not loads_data:
                    self._add_load_row_with_color(self.load_table, 0)

                self._save_name = file_name
                self.run_packing(display_msg=False)
                QtWidgets.QMessageBox.information(self, "Load Successful", "Data loaded successfully!")
            except (IOError, json.JSONDecodeError) as e:
                QtWidgets.QMessageBox.warning(self, "Load Error", f"Could not load file: {e}")
            except KeyError as e:
                QtWidgets.QMessageBox.warning(self, "Load Error", f"Invalid JSON format: Missing key {e}")

    def run_packing(self, *args, display_msg=True):
        """Run the 2D packing simulation using rectpack"""
        self.scene.clear()

        # Get container dimensions
        container_data = self._get_container()
        container_width = container_data['width']
        container_height = container_data['height']

        # Get items to pack
        items_to_pack = self._get_items_for_packing()

        if not items_to_pack and display_msg:
            QtWidgets.QMessageBox.warning(self, "No Items", "No items to pack!")
            return

        # Create a packer
        packer = rectpack.newPacker()

        # Add the bin (container)
        packer.add_bin(container_width, container_height)

        # Add rectangles to pack
        packed_items = []
        unpacked_items = []

        for i, (item_data, color) in enumerate(items_to_pack):
            width, height, name = item_data
            packer.add_rect(width, height, rid=i)
            packed_items.append((item_data, color))

        # Pack the rectangles
        packer.pack()

        # Draw the container
        self._draw_container(container_width, container_height)

        # Get packing results
        packed_rects = []
        unpacked_rects = []
        packed_ids = []

        try:
            for rect in packer[0]:  # First (and only) bin
                rid = rect.rid
                item_data, color = packed_items[rid]
                packed_rects.append((rect, item_data, color))
                packed_ids.append(rect.rid)
        except IndexError as e:
            pass
            
        for i, (item_data, color) in enumerate(packed_items):
            if i not in packed_ids:
                unpacked_rects.append((item_data, color))

        # Draw packed rectangles
        for rect, item_data, color in packed_rects:
            self._draw_item(rect.x, rect.y, rect.width, rect.height, item_data[2], color)
            
        self._zoom_to_fit()

        # Show results
        if unpacked_rects and display_msg:
            unpacked_names = [item[0][2] for item in unpacked_rects]
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setText("Some loads could not be fitted into the container:")
            msg.setInformativeText("\n".join(unpacked_names))
            msg.setWindowTitle("Packing Result")
            msg.exec()
        elif display_msg:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.setText("All loads fitted successfully!")
            msg.setWindowTitle("Packing Result")
            msg.exec()

    def _get_container(self):
        """Get container dimensions from the table"""
        row = 0
        name_item = self.container_table.item(row, 0)
        w_item = self.container_table.item(row, 1)
        h_item = self.container_table.item(row, 2)

        name = name_item.text() if name_item and name_item.text().strip() else "Container"
        w_text = w_item.text() if w_item and w_item.text().strip() else "10"
        h_text = h_item.text() if h_item and h_item.text().strip() else "10"

        try:
            width = float(w_text)
            height = float(h_text)
        except ValueError as e:
            print(f"Warning: Invalid container dimension. Defaulting to 10. Error: {e}")
            width, height = 10.0, 10.0

        return {'name': name, 'width': width, 'height': height}

    def _get_items_for_packing(self):
        """Get items to pack from the load table"""
        items_with_colors = []
        for row in range(self.load_table.rowCount()):
            name_item = self.load_table.item(row, 0)
            w_item = self.load_table.item(row, 1)
            h_item = self.load_table.item(row, 2)

            # Safely get text, default to "1" if item is None or text is empty
            w_text = w_item.text() if w_item and w_item.text().strip() else "1"
            h_text = h_item.text() if h_item and h_item.text().strip() else "1"

            try:
                width = float(w_text)
                height = float(h_text)
            except ValueError as e:
                print(f"Warning: Invalid dimension for row {row}. Defaulting to 1. Error: {e}")
                width, height = 1.0, 1.0

            item_color = self.load_row_colours.get(row, (0.5, 0.5, 0.5, 0.8))

            name = name_item.text() if name_item and name_item.text().strip() else f"Load {row + 1}"
            
            # Store as (width, height, name) tuple with color
            items_with_colors.append(((width, height, name), item_color))
        
        return items_with_colors

    def _draw_container(self, width, height):
        """Draw the container outline with axis labels and grid"""
        # Scale up the drawing by a factor to make it more visible
        scale_factor = 50  # Scale 1 meter = 50 pixels
        scaled_width = width * scale_factor
        scaled_height = height * scale_factor
        
        pen = QtGui.QPen(QtCore.Qt.white, 3)  # White container border
        brush = QtGui.QBrush(QtCore.Qt.transparent)
        
        # Draw container rectangle
        rect = self.scene.addRect(0, 0, scaled_width, scaled_height, pen, brush)
        
        # Add container label in white
        font = QtGui.QFont()
        font.setPointSize(14)
        text = self.scene.addText(f"Container ({width} × {height}m)", font)
        text.setDefaultTextColor(QtCore.Qt.white)
        text.setPos(scaled_width/2 - text.boundingRect().width()/2, -50)
        
        # Draw axis labels and tick marks
        self._draw_axes(width, height, scale_factor)
    
    def _draw_axes(self, width, height, scale_factor):
        """Draw axis labels, tick marks, and grid lines"""
        scaled_width = width * scale_factor
        scaled_height = height * scale_factor
        
        # Axis styling
        axis_pen = QtGui.QPen(QtCore.Qt.white, 2)
        tick_pen = QtGui.QPen(QtCore.Qt.white, 1)
        grid_pen = QtGui.QPen(QtGui.QColor(80, 80, 80), 1)  # Subtle grid lines
        
        font = QtGui.QFont()
        font.setPointSize(8)
        
        # Determine tick spacing (aim for reasonable number of ticks)
        x_tick_spacing = self._calculate_tick_spacing(width)
        y_tick_spacing = self._calculate_tick_spacing(height)
        
        # Draw X-axis (bottom)
        x_axis = self.scene.addLine(0, scaled_height, scaled_width, scaled_height, axis_pen)
        
        # X-axis ticks and labels
        x = 0
        while x <= width:
            scaled_x = x * scale_factor
            
            # Tick mark
            tick_line = self.scene.addLine(scaled_x, scaled_height, scaled_x, scaled_height + 10, tick_pen)
            
            # Grid line (vertical)
            if x > 0 and x < width:
                grid_line = self.scene.addLine(scaled_x, 0, scaled_x, scaled_height, grid_pen)
            
            # Label
            label = self.scene.addText(f"{x:.1f}", font)
            label.setDefaultTextColor(QtCore.Qt.white)
            label_rect = label.boundingRect()
            label.setPos(scaled_x - label_rect.width()/2, scaled_height + 15)
            
            x += x_tick_spacing
        
        # Draw Y-axis (left)
        y_axis = self.scene.addLine(0, 0, 0, scaled_height, axis_pen)
        
        # Y-axis ticks and labels
        y = 0
        while y <= height:
            scaled_y = scaled_height - (y * scale_factor)  # Flip Y coordinate
            
            # Tick mark
            tick_line = self.scene.addLine(-10, scaled_y, 0, scaled_y, tick_pen)
            
            # Grid line (horizontal)
            if y > 0 and y < height:
                grid_line = self.scene.addLine(0, scaled_y, scaled_width, scaled_y, grid_pen)
            
            # Label
            label = self.scene.addText(f"{y:.1f}", font)
            label.setDefaultTextColor(QtCore.Qt.white)
            label_rect = label.boundingRect()
            label.setPos(-label_rect.width() - 15, scaled_y - label_rect.height()/2)
            
            y += y_tick_spacing
        
        # Add axis titles
        # X-axis title
        x_title = self.scene.addText("Width (m)", font)
        x_title.setDefaultTextColor(QtCore.Qt.white)
        x_title_rect = x_title.boundingRect()
        x_title.setPos(scaled_width/2 - x_title_rect.width()/2, scaled_height + 50)
        
        # Y-axis title (rotated)
        y_title = self.scene.addText("Length (m)", font)
        y_title.setDefaultTextColor(QtCore.Qt.white)
        y_title.setRotation(-90)
        y_title_rect = y_title.boundingRect()
        y_title.setPos(-90, scaled_height/2 + y_title_rect.width()/2)
    
    def _calculate_tick_spacing(self, dimension):
        """Calculate appropriate tick spacing based on dimension"""
        if dimension <= 5:
            return 0.5
        elif dimension <= 10:
            return 1.0
        elif dimension <= 20:
            return 2.0
        elif dimension <= 50:
            return 5.0
        else:
            return 10.0

    def _draw_item(self, x, y, width, height, name, color_rgba):
        """Draw a packed item rectangle"""
        # Scale up the drawing by the same factor
        scale_factor = 50  # Scale 1 meter = 50 pixels
        scaled_x = x * scale_factor
        scaled_y = y * scale_factor
        scaled_width = width * scale_factor
        scaled_height = height * scale_factor
        
        r, g, b, a = color_rgba
        
        # Create color and pen with white borders
        qcolor = QtGui.QColor(int(r*255), int(g*255), int(b*255), int(a*255))
        pen = QtGui.QPen(QtCore.Qt.white, 1)  # White border for items
        brush = QtGui.QBrush(qcolor)
        
        # Draw rectangle
        rect = self.scene.addRect(scaled_x, scaled_y, scaled_width, scaled_height, pen, brush)
        
        # Add item label if rectangle is large enough
        min_text_size = 20  # Minimum size for text to be readable at scale
        if scaled_width > min_text_size and scaled_height > min_text_size/2:
            font = QtGui.QFont()
            font.setPointSize(10)
            text = self.scene.addText(name, font)
            text.setDefaultTextColor(QtCore.Qt.white)  # White text
            
            # Center the text in the rectangle
            text_rect = text.boundingRect()
            text_x = scaled_x + scaled_width/2 - text_rect.width()/2
            text_y = scaled_y + scaled_height/2 - text_rect.height()/2
            text.setPos(text_x, text_y)
            
            # Make text smaller if it still doesn't fit
            if text_rect.width() > scaled_width * 0.9 or text_rect.height() > scaled_height * 0.8:
                font.setPointSize(8)
                text.setFont(font)

    def _zoom_to_fit(self):
        """Zoom the view to fit all content"""
        if self.scene.items():
            self.canvas.fitInView(self.scene.itemsBoundingRect(), QtCore.Qt.KeepAspectRatio)
            # Add some padding
            self.canvas.scale(0.9, 0.9)




if __name__ == "__main__":
    import os

    app = QtWidgets.QApplication(sys.argv)
    stylesheet = """
        QMainWindow {
    background-color: #fdfdfd;
    }

    QMenuBar {
        background-color: #fafafa;
        color: #333;
        font-weight: bold;
        spacing: 8px;
        border-bottom: 1px solid #dcdcdc;
    }

    QMenuBar::item {
        background: transparent;
        padding: 6px 12px;
    }

    QMenuBar::item:selected {
        background: #e6f9ec;
        color: #00B140;
        border-radius: 4px;
    }

    QMenu {
        background-color: #ffffff;
        color: #333;
        border: 1px solid #ccc;
    }

    QMenu::item {
        padding: 6px 24px;
    }

    QMenu::item:selected {
        background-color: #d8f5e1;
        color: #00B140;
    }

        QPushButton {
            background-color: #00B140;
            color: white;
            border-radius: 6px;
            padding: 6px 12px;
            font-weight: bold;
        }

        QPushButton:hover {
            background-color: #009a37;
        }

        QPushButton:pressed {
            background-color: #007a2d;
        }

        QLabel {
            color: #222;
            font-size: 14px;
        }

        QTableWidget {
            background-color: white;
            gridline-color: #ddd;
            border: 1px solid #ccc;
            selection-background-color: #d8f5e1;
            selection-color: #000;
            font-size: 13px;
        }

        QHeaderView::section {
            background-color: #f4f4f4;
            padding: 6px;
            border: 1px solid #ccc;
            font-weight: bold;
            color: #333;
        }

        QHeaderView::section {
            text-transform: none;
        }

        QTableWidget QTableCornerButton::section {
            background: #f4f4f4;
            border: 1px solid #ccc;
        }

        QScrollBar:vertical, QScrollBar:horizontal {
            background: #f0f0f0;
            width: 12px;
            height: 12px;
            margin: 0px;
        }

        QScrollBar::handle {
            background: #c4e8cf;
            border-radius: 6px;
        }

        QScrollBar::handle:hover {
            background: #a8ddb9;
        }

        QScrollBar::add-line,
        QScrollBar::sub-line {
            background: none;
            border: none;
            width: 0px;
            height: 0px;
        }
        """


    app.setStyleSheet(stylesheet)
    viewer = PackingViewer()
    viewer.show()
    sys.exit(app.exec())