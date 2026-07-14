import os, csv, cv2, math
import pandas as pd
import numpy as np

from datetime           import datetime
from pathlib            import Path
from scipy.interpolate  import Akima1DInterpolator
from scipy.signal       import find_peaks, medfilt
from skimage.measure    import label, regionprops
from tkinter            import filedialog
from PyQt5.QtWidgets    import QGraphicsScene, QGraphicsPixmapItem
from PyQt5.QtGui        import QImage, QPixmap, QPainter
from PyQt5.QtCore       import Qt,QTimer, QRectF
from PyQt5.QtWidgets    import QDialog, QVBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox
from PyQt5.QtWidgets    import QProgressDialog

DEBUG = 0
#=========================================================================================
#  Viewing images for debug
#=========================================================================================
def VIEW_IMAGE(name, image):
    # Resize to a smaller window size (e.g., 800x600)
    resized = cv2.resize(image, (800, 600), interpolation=cv2.INTER_AREA)
    cv2.imshow(name, resized)
    cv2.waitKey(0)
    cv2.destroyAllWindows()    
#=========================================================================================
#  Dialog to resolve CLIENT ID
#=========================================================================================
from PyQt5.QtWidgets import (QLineEdit,  QLabel)

class NameInputDialog(QDialog):

    def __init__(self, parent=None):

        super().__init__(parent)
        self.setWindowTitle("ID Entry")
        self.resize(150, 120)
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        self.name = None

        layout = QVBoxLayout()

        self.label = QLabel("Please enter client ID:")
        layout.addWidget(self.label)

        self.lineEdit = QLineEdit()
        layout.addWidget(self.lineEdit)

        self.ok_button = QPushButton("OK")
        layout.addWidget(self.ok_button)

        self.ok_button.clicked.connect(self.get_name)
        
        self.setLayout(layout)

#---------------------------------------------------------------------------------------
    def get_name(self):

        entered_name = self.lineEdit.text().strip()
        if entered_name:
            self.name = entered_name
            self.accept()  # closes dialog with status = Accepted
        else:
            if not entered_name:
                QMessageBox.warning(self, "Warning", "No nameID given")
                self.accept()  # closes dialog with status = Accepted

#=========================================================================================
#  Dialog to resolve Client Selection
#=========================================================================================
class ClientSelectionDialog(QDialog):

    def __init__(self, data, headers=None, parent=None):

        super().__init__(parent)
        self.setWindowTitle("Click on the CLIENT ID")   
        self.selected_row = None

        layout = QVBoxLayout()
        self.table = QTableWidget()
        layout.addWidget(self.table)

        self.select_button = QPushButton("Select")
        self.select_button.clicked.connect(self.select_row)
        layout.addWidget(self.select_button)

        self.setLayout(layout)
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        self.populate_table(data, headers)
       
        # Resize table contents
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        self.table.horizontalHeader().setStretchLastSection(False)

        # Calculate actual table width (columns + row header + frame)
        table_width = self.table.verticalHeader().width()
        for i in range(self.table.columnCount()):
            table_width += self.table.columnWidth(i)
        table_width += 2 * self.table.frameWidth()

        # Calculate actual table height (rows + header + frame)
        table_height = self.table.horizontalHeader().height()
        for i in range(self.table.rowCount()):
            table_height += self.table.rowHeight(i)
        table_height += 2 * self.table.frameWidth()

        # Add room for the button and padding
        total_height = table_height + self.select_button.sizeHint().height() + 30

        # Set fixed size on the dialog
        self.setFixedSize(table_width + 40, total_height)

    #---------------------------------------------------------------------------------------
    def populate_table(self, data, headers):
        
        self.table.setRowCount(len(data))
        self.table.setColumnCount(data.shape[1] if not data.empty else 0)

        if headers:
            self.table.setHorizontalHeaderLabels(headers)

        for i, row in enumerate(data.values.tolist()):
            for j, val in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(str(val)))

#---------------------------------------------------------------------------------------
    def select_row(self):

        selected_items = self.table.selectedItems()
        if selected_items:
            self.selected_row = selected_items[0].row()
            self.accept()  # This closes the dialog and returns True from exec_()
        else:
            #QMessageBox.warning(self, "No Selection", "Please select a row before confirming.")
            self.selected_row = None  
            self.accept()    

#=========================================================================================
#  CLASSE PRINCIPAL
#=========================================================================================
class App:

    def __init__(self, atlas_name, ui):

        self.ui = ui  # reference to the MainWindow/UI
        self.ATLAS_name = atlas_name
        self.ATLAS   = None
        self.CLIENTS = None
        self.IMAGES  = None
        self.REPORT  = None
        self.DATES   = None

        self.CLIENT_TABLE = None

        self.RGB_fname  = None
        self.RGB_image  = None
        self.GUM_image  = None
        self.H_channel  = None
        self.Anamnesis  = None
        self.Image_Flag = 0
        self.Nx = 0
        self.Ny = 0
        self.left_X  = 0
        self.right_X = 0

#---------------------------------------------------------------------------------------
    def Exhibit_Image(self, image, locus):
        
        # Convert image from BGR to RGB
        IMAGE = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Convert to QImage
        #qimage = QImage(IMAGE.data, self.Nx, self.Ny, 3 * self.Nx, QImage.Format_RGB888)
        height, width, channels = IMAGE.shape
        qimage = QImage(IMAGE.data, width, height, channels * width, QImage.Format_RGB888)

        # Create a QPixmap
        pixmap = QPixmap.fromImage(qimage)
        self.pixmap_item = QGraphicsPixmapItem(pixmap)

        # Set up the scene
        scene = QGraphicsScene()
        scene.addItem(self.pixmap_item)
        scene.setSceneRect(QRectF(pixmap.rect()))  # REQUIRED

        # Attach scene to the graphics view
        view = locus
        view.setScene(scene)

        # These are CRITICAL for scaling to work:
        view.setRenderHint(QPainter.Antialiasing)
        view.setResizeAnchor(view.AnchorViewCenter)
        view.setTransformationAnchor(view.AnchorUnderMouse)
        view.setDragMode(view.ScrollHandDrag)
        view.setViewportUpdateMode(view.FullViewportUpdate)

        # Disable scrollbars completely
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Trigger fitInView after layout is completed
        QTimer.singleShot(0, lambda: view.fitInView(self.pixmap_item, Qt.KeepAspectRatio))
        #QTimer.singleShot(0, lambda: view.fitInView(self.pixmap_item, Qt.KeepAspectRatioByExpanding))

#---------------------------------------------------------------------------------------        
    def open_image_file(self):
        
        if DEBUG == 1:
            print(f"open_file_image invoked")
        
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.tif *.png")])

        if file_path:
            self.RGB_fname = file_path
            self.RGB_image = cv2.imread(self.RGB_fname)
            self.Nx = self.RGB_image.shape[1]
            self.Ny = self.RGB_image.shape[0]

            factor  = min(4800/self.Nx, 3200/self.Ny)
            Nx = math.floor(factor*self.Nx)
            Ny = math.floor(factor*self.Ny)
            self.RGB_image = cv2.resize(self.RGB_image, (Nx, Ny), interpolation=cv2.INTER_AREA)
            self.Nx = self.RGB_image.shape[1]
            self.Ny = self.RGB_image.shape[0]
            #print(self.Nx, self.Ny)

            if self.Image_Flag==2:
                self.ui.Processed_Image.scene().clear()
            self.ui.linePatientID.clear()
            self.ui.lineDate.clear()
            self.ui.Anamnesys.clear()
            self.Image_Flag = 1
            self.Anamnesis = ""
            image_info = f"iMAGE: {os.path.basename(file_path)}    SIZE: {self.Nx:4d} x {self.Ny:4d}"
            self.ui.ImageInfo.setText(image_info)
            self.Exhibit_Image(self.RGB_image, self.ui.Original_Image)
    
#---------------------------------------------------------------------------------------
    def ask_user_to_select_client(self):
        
        client_table = self.ATLAS.iloc[:, [0, 3]]
        dialog = ClientSelectionDialog(client_table, ["CLIENT ID", "DATE"], parent=self.ui)

        if dialog.exec_():
            if dialog.selected_row is not None:
                return dialog.selected_row
            
        return None

#---------------------------------------------------------------------------------------
    def Select_Client(self):

        if len(self.CLIENTS) == 0:
            QMessageBox.warning(None, "Warning", "Database empty")
        else:
            index = self.ask_user_to_select_client()
            #print(index)
            if index is not None:
                if DEBUG==1:
                    print("User selected row:", index)
                client_ID   = self.CLIENTS[index]
                client_date = self.DATES[index]
                self.RGB_fname = self.PATHS[index]
                self.RGB_image = cv2.imread(self.RGB_fname)
                self.Nx = self.RGB_image.shape[1]
                self.Ny = self.RGB_image.shape[0]
                self.Image_Flag = 1
                self.GUM_image = None
                if self.ui.Processed_Image.scene():
                    self.ui.Processed_Image.scene().clear()
                with open(self.REPORT[index], "r", encoding="utf-8") as file:
                    content = file.read()
                self.ui.Anamnesys.setText(content)
                self.Exhibit_Image(self.RGB_image, self.ui.Original_Image)
                self.ui.linePatientID.setText(client_ID)
                self.ui.lineDate.setText(client_date)
            else:
                if DEBUG==1:
                    print("User canceled selection.")

#---------------------------------------------------------------------------------------
    def Save_Client(self):

        dialog =  NameInputDialog(parent=self.ui)
        if dialog.exec_():
            if DEBUG==1:
                print(dialog.name)
            if dialog.name != None:
                cur_date  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                file_path = Path(self.RGB_fname)
                anm_fname = file_path.with_suffix(".txt")
                with open(anm_fname, "w", encoding="utf-8") as file:
                    text = self.ui.Anamnesys.toPlainText()
                    file.write(text)
                row = [dialog.name, self.RGB_fname, anm_fname, cur_date]
                with open(self.ATLAS_name, "a", newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(row)  
                self.read_atlas()          
        else:    
            QMessageBox.warning(self, "Missing", "No nameID given")

#---------------------------------------------------------------------------------------
    def clear_images(self, caso):

        self.RGB_image = None
        self.GUM_image = None
        self.Image_Flag = 0
        if self.ui.Original_Image.scene():
            self.ui.Original_Image.scene().clear()
        if self.ui.Processed_Image.scene():
            self.ui.Processed_Image.scene().clear()
        self.ui.linePatientID.clear()
        self.ui.lineDate.clear()
        self.ui.Anamnesys.clear()
        if caso==2: 
            if self.ui.Original_Image_Copy.scene():
                self.ui.Original_Image_Copy.scene().clear()
            if self.ui.Processed_Image_Copy.scene():
                self.ui.Processed_Image_Copy.scene().clear()
            self.ui.linePatientID_Copy.clear()
            self.ui.lineDate_Copy.clear()
            self.ui.Anamnesys_Copy.clear()
        
#---------------------------------------------------------------------------------------
    def move_down_images(self):  

        if self.Image_Flag >= 1:
            self.Exhibit_Image(self.RGB_image, self.ui.Original_Image_Copy) 
        if self.Image_Flag >= 2:
            self.Exhibit_Image(self.GUM_image, self.ui.Processed_Image_Copy) 
        self.ui.linePatientID_Copy.setText(self.ui.linePatientID.text()) 
        self.ui.lineDate_Copy.setText(self.ui.lineDate.text()) 
        self.ui.Anamnesys_Copy.setPlainText(self.ui.Anamnesys.toPlainText())   

#---------------------------------------------------------------------------------------
    def read_atlas(self):
  
        if not os.path.exists(self.ATLAS_name):
            data = ["ClientID", "ImageFile", "TextFile", "Date"]
            with open(self.ATLAS_name, mode="w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(data)
    
        # Read the ATLAS table
        self.ATLAS = pd.read_csv(self.ATLAS_name)  # Adjust if file format is not CSV
        ATLAS_size = len(self.ATLAS)
        if DEBUG == 1:
            print(f"Atlas read with {ATLAS_size} rows")
        self.ui.PatCounter.setText(str(ATLAS_size))

        # Extract clients and dates from the ATLAS table
        self.CLIENTS = self.ATLAS.iloc[:, 0].values    # Assuming client codes are in the first column
        self.PATHS   = self.ATLAS.iloc[:, 1].values    # Assuming image paths  are in the second column
        self.REPORT  = self.ATLAS.iloc[:, 2].values    # Assuming report paths are in the third column
        self.DATES   = self.ATLAS.iloc[:, 3].values    # Assuming dates        are in the fourth column


#---------------------------------------------------------------------------------------
#  All routines bellow are related to the Image Processing
#---------------------------------------------------------------------------------------
    def hue_to_degrees(self, x):
        """
        First,  converts [0, 179] hue range    into [0, 360]   degree range.
        Second, converts [0, 360] degree range into [-180,180] degree range.
        
        Parameters:
            x (array-like or float): Input value(s) in the hue range [0, 179].
            
        Returns:
            y (array-like or float): Converted value(s) in the range [-180, 180].
        """
        # Scale the input to degree range [0, 360]
        y = np.round(2.0112 * x)
        
        # Adjust degree values greater than 180 to the range [-180,0]
        y[y > 180] -= 360
        
        return y
    
#---------------------------------------------------------------------------------------
    def hue_threshold(self, h_channel):
        """
        Detects the boundary between teeth and gum by mean of hue histogram peaks.

        Parameters:
            h_channel (array-like): Input hue values in the range [-180, 180].

        Returns:
            bound (float): Boundary value in the degree range [-15, 40].
        """

        phase = h_channel.flatten()

        # Create histogram in the range [-15, 40]
        edges = np.arange(-15, 42, 2)  # Edges from -15 to 40 with step 2
        y, _  = np.histogram(phase, bins=edges, density=True)

        bin_width = edges[1] - edges[0]
        x = edges[:-1] + bin_width / 2  # Midpoints of bins
        
        # Smooth histogram using Akima interpolation
        xP = np.linspace(x[0], x[-1], 80)  # Interpolated x values
        akima_interpolator = Akima1DInterpolator(x, y)
        yP = akima_interpolator(xP)  # Smoothed histogram

        # Find valleys in the smoothed histogram
        peaks, properties = find_peaks(-yP,prominence=0.001)  # Negate yP to find valleys
        x_valleys  = xP[peaks]
        prominence = properties["prominences"]

        if len(prominence) > 0:
            most_prominent_index = np.argmax(prominence)
            bound = x_valleys[most_prominent_index]
        else:
            bound = None  # Handle case with no valleys
        if bound==None:
            bound = 15
    
        return bound
    
#---------------------------------------------------------------------------------------
    def hue_filter(self, h_channel, hue_range):
        """
        Applies a filter to the hue channel based on the specified range.
        Updates the hue channel where values fall outside the range.

        Parameters:
            h_channel (numpy.ndarray): Input hue channel (values in the range [0, 179]).
            hue_range (tuple): Hue range as (minHue, maxHue) in degrees [0, 360].

        Returns:
            numpy.ndarray: Binary mask indicating filtered regions.
        """
        [min_hue, max_hue] = hue_range

        # Create the mask based on the specified range
        if min_hue <= max_hue:
            mask_h = (h_channel <  min_hue) | (h_channel >  max_hue)
        else:
            mask_h = (h_channel >= max_hue) & (h_channel <= min_hue)

        # Set the filtered regions in the hue channel to 0
        h_channel[mask_h] = 0

        return mask_h
    
#---------------------------------------------------------------------------------------
    def mask_image(self, rgb_image, mask):
        """
        Applies a binary mask to an RGB image.

        Parameters:
            rgb_image (numpy.ndarray): Input RGB image as a 3D NumPy array (H, W, 3).
            mask (numpy.ndarray): Binary mask as a 2D NumPy array (H, W).

        Returns:
            numpy.ndarray: Masked RGB image as a 3D NumPy array.
        """
        # Ensure dimensions match
        assert rgb_image.shape[:2] == mask.shape, "Dimensions of the image and mask do not match."

        # Initialize the masked image with the same shape and data type as the input image
        masked_image = np.zeros_like(rgb_image)

        # Apply the mask to each channel
        masked_image[:, :, 0] = rgb_image[:, :, 0] * mask  # Red   channel
        masked_image[:, :, 1] = rgb_image[:, :, 1] * mask  # Green channel
        masked_image[:, :, 2] = rgb_image[:, :, 2] * mask  # Blue  channel

        return masked_image
    
#---------------------------------------------------------------------------------------
    def find_teeth_location(self, mask):
        """
        Finds the locations of teeth in a binary mask by detecting peaks and valleys.

        Parameters:
            mask (numpy.ndarray): Binary mask with teeth regions.

        Returns:
            LOCUS (list of numpy.ndarray): x-coordinates of peaks (teeth locations) for each arcade.
            PICOS (list of numpy.ndarray): Peak values for each arcade.
            POSIC (list of numpy.ndarray): x-coordinates of valleys for each arcade.
            VALES (list of numpy.ndarray): Valley values for each arcade.
        """
        
        proem_min  =     2  # Minimum peak prominence
        dist_min   =   150  # Minimum peak distance
        height_min = -4000  # Minimum peak height
        
        jaw = ["superior", "inferior"]

        # Initialize results
        LOCUS = [None, None]  # x-coordinates of peaks
        PICOS = [None, None]  # Peak values
        POSIC = [None, None]  # x-coordinates of valleys
        VALES = [None, None]  # Valley values

        # Sum mask along the vertical axis to get the horizontal profile
        w = np.sum(mask, axis=0)
        self.left_X  = np.argmax(w > 0)                     # First non-zero column
        self.right_X = len(w) - np.argmax(w[::-1] > 0) - 1  # Last  non-zero column
        arcade  = np.zeros((self.right_X - self.left_X + 1, 2), dtype=int)

        # Extract the first and last non-zero pixel positions in the vertical direction
        range_x = np.arange(self.left_X, self.right_X + 1)
        for pos, k in enumerate(range_x):
            r = mask[:, k]
            arcade[pos, 0] = np.argmax(r > 0)                     # First non-zero vertical pixel
            arcade[pos, 1] = len(r) - np.argmax(r[::-1] > 0) - 1  # Last non-zero vertical pixel

        # Adjust for the y-origin being at the top
        arcade[:, 0] = mask.shape[0] - arcade[:, 0]
        
        # Find peaks and valleys for both arcs
        for k in range(2):
            # Find pea*ks
            peak_pos, p_properties = find_peaks(arcade[:, k], height=height_min, distance=dist_min, prominence=proem_min)
            LOCUS[k] = peak_pos + self.left_X
            PICOS[k] = p_properties['peak_heights']
    
            # Find valleys
            neg_arcade = -arcade[:, k]
            vale_pos, v_properties = find_peaks(neg_arcade, height=height_min, distance=dist_min, prominence=proem_min)
            POSIC[k] = vale_pos + self.left_X 
            VALES[k] = -v_properties['peak_heights']
        
        return LOCUS, PICOS, POSIC, VALES
    
    #---------------------------------------------------------------------------------------
    def Remove_Small_Objects(self, image, min_size):

        # Perform connected components analysis
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(image, connectivity=8)

        # Create a blank mask for filtering
        image_rem = np.zeros_like(image)
        
        # Keep only large components
        for i in range(1, num_labels):  # Skip the background (label 0)
            if stats[i, cv2.CC_STAT_AREA] > min_size:
                image_rem[labels == i] = 255
        """
        # Exclude background (index 0)
        component_areas = stats[1:, cv2.CC_STAT_AREA]

        # Get the index of the max area in the sliced array
        max_index = np.argmax(component_areas)

        # Correct the index since we sliced off background
        max_label = max_index + 1               
        image_rem[labels == max_label] = 255
        """
        return image_rem
    
#---------------------------------------------------------------------------------------
    def Fill_Holes(self, image):

        inverted = cv2.bitwise_not(image)
        clean = self.Remove_Small_Objects(inverted, 30000)
        filled = cv2.bitwise_not(clean)

        return filled
    
#---------------------------------------------------------------------------------------
    def Select_Largest_Object(self, image):

        labeled = label(image)
        regions = regionprops(labeled)
        if len(regions)==0:
            biggest = 0
            flag = 1
        else:
            largest_region = max(regions, key=lambda r: r.area)
            largest_mask = labeled == largest_region.label
            biggest = 255*largest_mask.astype(np.uint8)
            flag = 0

        return biggest, flag
#---------------------------------------------------------------------------------------
    def process_gums(self, case, peaks, valleys, criterion, mean_hue, jaw, boundary, tol):
        
        mascara = np.zeros((self.Ny, self.Nx), dtype=bool)
        top     = np.sort(np.concatenate((peaks, valleys)))
   
        # Removing small intervals from tooth boundaries
        topx = np.zeros_like(top)  
        topx[0] = top[0]
        pos = 1
        for k in range(1,len(top)):
            if top[k]-top[k-1] > 100:
                topx[pos] = top[k]
                pos = pos + 1      
        top = topx[:pos]

        GUESS   = np.zeros(self.Nx, dtype=np.uint8)
        MED_H   = np.zeros(self.Nx)
        HUE_H   = mean_hue

        for m in range(len(top) - 1):
            RANGE = np.arange(top[m], top[m + 1])
            HUE_VALS = HUE_H[RANGE]
            PIECE = np.mean(HUE_VALS)
            MED_H[RANGE] = PIECE
            
            if criterion == 0:
                if PIECE < jaw - tol:
                    GUESS[RANGE] = 1
            else:
                HUE_VALS = HUE_VALS - jaw + tol
                idx = HUE_VALS <= 0
                R = -np.sum(HUE_VALS[idx]) / np.sum(np.abs(HUE_VALS))
                if R >= 0.3:
                    GUESS[RANGE] = 1
        factor = np.sum(GUESS) / (self.right_X - self.left_X)                     
        v_mask = np.ones(self.Ny, dtype=bool)
        if case==0:
            v_mask[boundary:] = 0
        else:
            v_mask[:boundary] = 0
        mascara[np.outer(v_mask, GUESS.astype(bool))] = 1

        return factor, mascara
    
#---------------------------------------------------------------------------------------
    def process_image(self):

        # Convert RGB to HSV    H channel ranges from 0 to 179 (in OpenCV)
        hsv_image = cv2.cvtColor(self.RGB_image, cv2.COLOR_BGR2HSV)
        h_channel = self.hue_to_degrees(hsv_image[:, :, 0])    # hue in tne range[-180,180]
        self.H_channel = h_channel

        # Hue thresholding
        h_bound = self.hue_threshold(h_channel)

        # Generating initial mask
        h_range = [-10, h_bound]
        maskB   = self.hue_filter(h_channel, h_range)
        maskI   = maskB.astype(np.uint8)
        maskG   = 255*maskI
        #VIEW_IMAGE('maskG', maskG)

        # Remove small objects
        REMOVE_SIZE  = 100000
        maskG_rem = self.Remove_Small_Objects(maskG, REMOVE_SIZE)
        #VIEW_IMAGE('maskG_rem', maskG_rem)

        # Filling holes  
        maskG_filled = self.Fill_Holes(maskG_rem)
        #VIEW_IMAGE('maskG_filled', maskG_filled)

        # Selecting the biggest object
        biggest, flag = self.Select_Largest_Object(maskG_filled)
        #VIEW_IMAGE('biggest', biggest)

        if flag==0:
            maskG_biggest = biggest
        else:
            QMessageBox.warning(None, "Warning", "Imagem com baixa resolução.")   
            return

        # "Sanding" the biggest object 
        CLOSE_SE_SIZE = 20
        se   = np.ones((CLOSE_SE_SIZE, CLOSE_SE_SIZE))
        temp = cv2.morphologyEx(maskG_biggest, cv2.MORPH_CLOSE, se)
        maskG_sanded = self.Fill_Holes(temp)
        
        # Find inner contour
        inner_contour, _ = cv2.findContours(maskG_sanded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Find outer countour
        GUM_SIZE = 210
        se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (GUM_SIZE, GUM_SIZE))
        maskG_dilated    = cv2.dilate(maskG_sanded, se) 
        outer_contour, _ = cv2.findContours(maskG_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Gum R.o.I. mask
        maskB_gumRoi = (maskG_dilated - maskG_sanded).astype(bool)
        maskI_gumRoi = maskB_gumRoi.astype(np.uint8)

        # Find lateral boundaries of the mask
        MARGIN = 0
        sum_mask    = np.sum(maskG_sanded, axis=0)
        left_bound  = MARGIN + np.argmax(sum_mask > 0)
        right_bound = len(sum_mask) - np.argmax(sum_mask[::-1] > 0) - MARGIN
    
        # Boundary between uper and lower gum
        density   = np.sum(maskG_sanded, axis=1)
        top       = np.argmax(density > 0)
        bottom    = len(density) - np.argmax(density[::-1] > 0)
        threshold = np.round((top + bottom)/2).astype(np.uint64)
        
        # Split and analyze masks for superior and inferior
        masks = {"superior": None, "inferior": None}
        gums  = {"superior": None, "inferior": None}
        means = {"superior": 0,    "inferior": 0}

        for side, region in [("superior", (threshold, self.Ny)), ("inferior", (0, threshold))]:
            mask_side = maskB_gumRoi.copy()
            mask_side[region[0]:region[1], :] = 0
            mask_side[:, :left_bound]  = 0
            mask_side[:, right_bound:] = 0
        
            hue_vals    = h_channel[mask_side]
            means[side] = np.mean(self.hue_to_degrees(hue_vals))     # global hue mean
            masks[side] = mask_side
            gums[side]  = self.mask_image(self.RGB_image, mask_side)    

        # Overlay mask onto the ROI
        mask_combined = masks["superior"] | masks["inferior"]
        image_final   = self.mask_image(self.RGB_image, mask_combined)
        #VIEW_IMAGE('image_final', image_final)

        # Generating redness curves
        SMOOTH_PARAM = 99   # TEM QUE SER IMPAR

        mean_hue = np.zeros((self.Nx, 2))
        for idx, side in enumerate(["superior", "inferior"]):
            mask_side = masks[side]
            for col in range(self.Nx):
                temp = np.sum(mask_side[:, col])
                col_vals = h_channel[mask_side[:, col], col]
                if col_vals.size > 0:
                    mean_hue[col, idx] = np.mean(self.hue_to_degrees(col_vals))

            # Smooth using a median filter
            mean_hue[:, idx] = medfilt(mean_hue[:, idx], SMOOTH_PARAM) 

        RedTol    = 0  # Tolerance for recommendation
        CRITERION = 1   

        # Finding Teeth detection
        TEETH, _, TOOTH, _ = self.find_teeth_location(maskG_dilated.astype(bool))
        if len(TEETH[0])==0 or len(TEETH[1])==0 or len(TOOTH[0])==0 or len(TOOTH[0])==0:
            QMessageBox.warning(None, "Warning", "Dificuldade de identificação dos dentes.")   
            return  
          
        factor1, M1 = self.process_gums( 0, TEETH[0], TOOTH[0], 1, mean_hue[:, 0], means['superior'], threshold, RedTol)
        factor2, M2 = self.process_gums( 1, TEETH[1], TOOTH[1], 1, mean_hue[:, 1], means['inferior'], threshold, RedTol)
        info    = f"Sup.Infection = {100*factor1:5.2f} % Inf.Infection = {100*factor2:5.2f} %"
        self.ui.Anamnesys.append(info)

        # Combining everything 
        MASCARA = (M1 | M2) & maskB_gumRoi
        MASK1 = MASCARA.astype(np.uint8)
        MASK2 = 1 - MASK1

        image_final[:,:,2] = image_final[:,:,2]*MASK2 + 255*MASK1
        image_final[:,:,1] = image_final[:,:,1]*MASK2
        image_final[:,:,0] = image_final[:,:,0]*MASK2
        self.GUM_image = image_final
        self.Image_Flag = 2

        self.Exhibit_Image(self.GUM_image, self.ui.Processed_Image)

#---------------------------------------------------------------------------------------
    def gum_process(self):

        if self.Image_Flag >= 1:            
            self.process_image()
       
    def run_task_with_wait_message(self):
        self.progress_dialog = QProgressDialog(
            "Please wait while the task completes...", None, 0, 0, self.ui
        )
        self.progress_dialog.setWindowTitle("Working...")
        self.progress_dialog.setWindowFlags(
            Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint
        )
        self.progress_dialog.setWindowModality(Qt.ApplicationModal)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

        QTimer.singleShot(100, self.long_task)

    def long_task(self):
        self.process_image()
        self.progress_dialog.close()

                 
#=======================================================================================
