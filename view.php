<?php 
session_start();

// cek apakah yang mengakses halaman ini sudah login
    if($_SESSION['level']==""){
    header("location:index.php?pesan=gagal");
  }

require 'funcition.php';

$id = $_GET["id"];
        $sql    =mysqli_query($conn,"SELECT * FROM soal WHERE id='$id'");

?>

<!DOCTYPE html>
<html>
<head>
    <link rel="icon" href="icon/hexagonos.jpg">
    <title>Ujian Test</title>
    <link rel="stylesheet" href="assets/css/bootstrap.min.css">
</head>
<body>
<div class="container ">
   
        <div class="container">
  
 <table class="table table-bordered mt-5">
  <thead class="bg-primary text-white">
  <tr>
                <th>Pertanyaan</th>
                <th>A</th>
                <th>B</th>
                <th>C</th>
                <th>D</th>
                <th>Jawaban</th>
            </tr>
</thead>
<tbody>
<?php
                while($row=mysqli_fetch_assoc($sql))
                    {
            ?>
  <tr>
                <td><?php echo $row['soal'];?></td>
                <td><?php echo $row['a'];?></td>
                <td><?php echo $row['b'];?></td>
                <td><?php echo $row['c'];?></td>
                <td><?php echo $row['d'];?></td>
                <td><?php echo $row['kunci'];?></td>
            </tr>
  <?php
                    }
            ?>
</tbody>
</table>
<a href="halaman_admin.php" class="btn btn-dark ">Back</a>
</div>

</div>

<!-- Optional JavaScript -->
    <!-- jQuery first, then Popper.js, then Bootstrap JS -->
    <script src="assets/jquery-3.4.1.slim.min.js" ></script>
    <script src="assets/popper.min.js" ></script>
    <script src="assets/js/bootstrap.min.js" ></script>
</body>
</html>